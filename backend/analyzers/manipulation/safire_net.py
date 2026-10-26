import math
from functools import partial

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

IMG_SIZE = 1024
PATCH = 16
EMBED_DIM = 768
DEPTH = 12
HEADS = 12
GLOBAL_ATTN = (2, 5, 8, 11)
WINDOW = 14
PROMPT_DIM = 256
ADAPTOR_SCALE = 4
PIXEL_MEAN = (123.675, 116.28, 103.53)
PIXEL_STD = (58.395, 57.12, 57.375)


class MLPBlock(nn.Module):
    def __init__(self, embedding_dim, mlp_dim, act=nn.GELU):
        super().__init__()
        self.lin1 = nn.Linear(embedding_dim, mlp_dim)
        self.lin2 = nn.Linear(mlp_dim, embedding_dim)
        self.act = act()

    def forward(self, x):
        return self.lin2(self.act(self.lin1(x)))


class LayerNorm2d(nn.Module):
    def __init__(self, num_channels, eps=1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(num_channels))
        self.bias = nn.Parameter(torch.zeros(num_channels))
        self.eps = eps

    def forward(self, x):
        u = x.mean(1, keepdim=True)
        s = (x - u).pow(2).mean(1, keepdim=True)
        x = (x - u) / torch.sqrt(s + self.eps)
        return self.weight[:, None, None] * x + self.bias[:, None, None]


class PatchEmbed(nn.Module):
    def __init__(self, kernel_size, stride, padding=(0, 0), in_chans=3, embed_dim=EMBED_DIM):
        super().__init__()
        self.proj = nn.Conv2d(in_chans, embed_dim, kernel_size=kernel_size, stride=stride, padding=padding)

    def forward(self, x):
        return self.proj(x).permute(0, 2, 3, 1)


def window_partition(x, window_size):
    b, h, w, c = x.shape
    pad_h = (window_size - h % window_size) % window_size
    pad_w = (window_size - w % window_size) % window_size
    if pad_h or pad_w:
        x = F.pad(x, (0, 0, 0, pad_w, 0, pad_h))
    hp, wp = h + pad_h, w + pad_w
    x = x.view(b, hp // window_size, window_size, wp // window_size, window_size, c)
    return x.permute(0, 1, 3, 2, 4, 5).contiguous().view(-1, window_size, window_size, c), (hp, wp)


def window_unpartition(windows, window_size, pad_hw, hw):
    hp, wp = pad_hw
    h, w = hw
    b = windows.shape[0] // (hp * wp // window_size // window_size)
    x = windows.view(b, hp // window_size, wp // window_size, window_size, window_size, -1)
    x = x.permute(0, 1, 3, 2, 4, 5).contiguous().view(b, hp, wp, -1)
    if hp > h or wp > w:
        x = x[:, :h, :w, :].contiguous()
    return x


def get_rel_pos(q_size, k_size, rel_pos):
    max_rel_dist = int(2 * max(q_size, k_size) - 1)
    if rel_pos.shape[0] != max_rel_dist:
        resized = F.interpolate(rel_pos.reshape(1, rel_pos.shape[0], -1).permute(0, 2, 1), size=max_rel_dist, mode="linear")
        resized = resized.reshape(-1, max_rel_dist).permute(1, 0)
    else:
        resized = rel_pos
    q_coords = torch.arange(q_size)[:, None] * max(k_size / q_size, 1.0)
    k_coords = torch.arange(k_size)[None, :] * max(q_size / k_size, 1.0)
    relative = (q_coords - k_coords) + (k_size - 1) * max(q_size / k_size, 1.0)
    return resized[relative.long()]


def add_decomposed_rel_pos(attn, q, rel_pos_h, rel_pos_w, q_size, k_size):
    q_h, q_w = q_size
    k_h, k_w = k_size
    rh = get_rel_pos(q_h, k_h, rel_pos_h)
    rw = get_rel_pos(q_w, k_w, rel_pos_w)
    b, _, dim = q.shape
    r_q = q.reshape(b, q_h, q_w, dim)
    rel_h = torch.einsum("bhwc,hkc->bhwk", r_q, rh)
    rel_w = torch.einsum("bhwc,wkc->bhwk", r_q, rw)
    attn = attn.view(b, q_h, q_w, k_h, k_w) + rel_h[:, :, :, :, None] + rel_w[:, :, :, None, :]
    return attn.view(b, q_h * q_w, k_h * k_w)


class ViTAttention(nn.Module):
    def __init__(self, dim, num_heads, input_size):
        super().__init__()
        self.num_heads = num_heads
        head_dim = dim // num_heads
        self.scale = head_dim**-0.5
        self.qkv = nn.Linear(dim, dim * 3, bias=True)
        self.proj = nn.Linear(dim, dim)
        self.rel_pos_h = nn.Parameter(torch.zeros(2 * input_size[0] - 1, head_dim))
        self.rel_pos_w = nn.Parameter(torch.zeros(2 * input_size[1] - 1, head_dim))

    def forward(self, x):
        b, h, w, _ = x.shape
        qkv = self.qkv(x).reshape(b, h * w, 3, self.num_heads, -1).permute(2, 0, 3, 1, 4)
        q, k, v = qkv.reshape(3, b * self.num_heads, h * w, -1).unbind(0)
        attn = (q * self.scale) @ k.transpose(-2, -1)
        attn = add_decomposed_rel_pos(attn, q, self.rel_pos_h, self.rel_pos_w, (h, w), (h, w))
        attn = attn.softmax(dim=-1)
        x = (attn @ v).view(b, self.num_heads, h, w, -1).permute(0, 2, 3, 1, 4).reshape(b, h, w, -1)
        return self.proj(x)


class ViTBlock(nn.Module):
    def __init__(self, dim, num_heads, window_size, input_size):
        super().__init__()
        norm = partial(nn.LayerNorm, eps=1e-6)
        self.norm1 = norm(dim)
        self.attn = ViTAttention(dim, num_heads, input_size if window_size == 0 else (window_size, window_size))
        self.norm2 = norm(dim)
        self.mlp = MLPBlock(dim, int(dim * 4.0))
        self.window_size = window_size

    def forward(self, x):
        shortcut = x
        x = self.norm1(x)
        if self.window_size > 0:
            h, w = x.shape[1], x.shape[2]
            x, pad_hw = window_partition(x, self.window_size)
        x = self.attn(x)
        if self.window_size > 0:
            x = window_unpartition(x, self.window_size, pad_hw, (h, w))
        x = shortcut + x
        return x + self.mlp(self.norm2(x))


def highpass(x, rate=0.25):
    h, w = x.shape[-2:]
    line = int((h * w * rate) ** 0.5 // 2)
    mask = torch.ones_like(x)
    mask[:, :, h // 2 - line : h // 2 + line, w // 2 - line : w // 2 + line] = 0
    spec = torch.fft.fftshift(torch.fft.fft2(x, norm="forward")) * mask
    return torch.fft.ifft2(torch.fft.ifftshift(spec), norm="forward").real.abs()


class AdaptorImageEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.img_size = IMG_SIZE
        tokens = IMG_SIZE // PATCH
        self.patch_embed = PatchEmbed((PATCH, PATCH), (PATCH, PATCH))
        self.hfp_overlap_patch_embed = PatchEmbed((PATCH * 2, PATCH * 2), (PATCH, PATCH), (PATCH // 2, PATCH // 2))
        small = EMBED_DIM // ADAPTOR_SCALE
        self.adaptor_patch_embed_tune = nn.Linear(EMBED_DIM, small)
        self.hfp_patch_embed_tune = nn.Linear(EMBED_DIM, small)
        self.pos_embed = nn.Parameter(torch.zeros(1, tokens, tokens, EMBED_DIM))
        self.blocks = nn.ModuleList(
            [
                ViTBlock(EMBED_DIM, HEADS, 0 if i in GLOBAL_ATTN else WINDOW, (tokens, tokens))
                for i in range(DEPTH)
            ]
        )
        self.adaptor_shared_up_projection_layer = nn.Linear(small, EMBED_DIM)
        self.adaptor_blocks = nn.ModuleList([nn.Sequential(nn.Linear(small, small), nn.GELU()) for _ in range(DEPTH)])
        self.adaptor_final_block = nn.Sequential(nn.Linear(small, small), nn.GELU())
        self.neck = nn.Sequential(
            nn.Conv2d(EMBED_DIM, PROMPT_DIM, kernel_size=1, bias=False),
            LayerNorm2d(PROMPT_DIM),
            nn.Conv2d(PROMPT_DIM, PROMPT_DIM, kernel_size=3, padding=1, bias=False),
            LayerNorm2d(PROMPT_DIM),
        )

    def forward(self, x):
        y_embed = self.hfp_overlap_patch_embed(highpass(x))
        x_embed = self.patch_embed(x) + self.pos_embed
        tuned = self.adaptor_patch_embed_tune(x_embed) + self.hfp_patch_embed_tune(y_embed)
        x = x_embed
        for blk, adaptor in zip(self.blocks, self.adaptor_blocks):
            x = x + self.adaptor_shared_up_projection_layer(adaptor(tuned))
            x = blk(x)
        x = x + self.adaptor_shared_up_projection_layer(self.adaptor_final_block(tuned))
        return self.neck(x.permute(0, 3, 1, 2))


class PositionEmbeddingRandom(nn.Module):
    def __init__(self, num_pos_feats=64):
        super().__init__()
        self.register_buffer("positional_encoding_gaussian_matrix", torch.randn((2, num_pos_feats)))

    def _pe_encoding(self, coords):
        coords = 2 * coords - 1
        coords = coords @ self.positional_encoding_gaussian_matrix
        coords = 2 * np.pi * coords
        return torch.cat([torch.sin(coords), torch.cos(coords)], dim=-1)

    def forward(self, size):
        h, w = size
        grid = torch.ones((h, w), dtype=torch.float32)
        y_embed = (grid.cumsum(dim=0) - 0.5) / h
        x_embed = (grid.cumsum(dim=1) - 0.5) / w
        return self._pe_encoding(torch.stack([x_embed, y_embed], dim=-1)).permute(2, 0, 1)

    def forward_with_coords(self, coords_input, image_size):
        coords = coords_input.clone()
        coords[:, :, 0] = coords[:, :, 0] / image_size[1]
        coords[:, :, 1] = coords[:, :, 1] / image_size[0]
        return self._pe_encoding(coords.to(torch.float))


class PromptEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.embed_dim = PROMPT_DIM
        tokens = IMG_SIZE // PATCH
        self.input_image_size = (IMG_SIZE, IMG_SIZE)
        self.image_embedding_size = (tokens, tokens)
        self.pe_layer = PositionEmbeddingRandom(PROMPT_DIM // 2)
        self.point_embeddings = nn.ModuleList([nn.Embedding(1, PROMPT_DIM) for _ in range(4)])
        self.not_a_point_embed = nn.Embedding(1, PROMPT_DIM)
        self.mask_downscaling = nn.Sequential(
            nn.Conv2d(1, 4, kernel_size=2, stride=2),
            LayerNorm2d(4),
            nn.GELU(),
            nn.Conv2d(4, 16, kernel_size=2, stride=2),
            LayerNorm2d(16),
            nn.GELU(),
            nn.Conv2d(16, PROMPT_DIM, kernel_size=1),
        )
        self.no_mask_embed = nn.Embedding(1, PROMPT_DIM)

    def get_dense_pe(self):
        return self.pe_layer(self.image_embedding_size).unsqueeze(0)

    def embed_points(self, points, labels):
        points = points + 0.5
        pad_point = torch.zeros((points.shape[0], 1, 2))
        pad_label = -torch.ones((labels.shape[0], 1))
        points = torch.cat([points, pad_point], dim=1)
        labels = torch.cat([labels, pad_label], dim=1)
        emb = self.pe_layer.forward_with_coords(points, self.input_image_size)
        emb[labels == -1] = 0.0
        emb[labels == -1] += self.not_a_point_embed.weight
        emb[labels == 0] += self.point_embeddings[0].weight
        emb[labels == 1] += self.point_embeddings[1].weight
        return emb

    def forward(self, points, labels):
        sparse = self.embed_points(points, labels)
        dense = self.no_mask_embed.weight.reshape(1, -1, 1, 1).expand(
            points.shape[0], -1, self.image_embedding_size[0], self.image_embedding_size[1]
        )
        return sparse, dense


class Attention(nn.Module):
    def __init__(self, embedding_dim, num_heads, downsample_rate=1):
        super().__init__()
        self.internal_dim = embedding_dim // downsample_rate
        self.num_heads = num_heads
        self.q_proj = nn.Linear(embedding_dim, self.internal_dim)
        self.k_proj = nn.Linear(embedding_dim, self.internal_dim)
        self.v_proj = nn.Linear(embedding_dim, self.internal_dim)
        self.out_proj = nn.Linear(self.internal_dim, embedding_dim)

    def _separate(self, x):
        b, n, c = x.shape
        return x.reshape(b, n, self.num_heads, c // self.num_heads).transpose(1, 2)

    def forward(self, q, k, v):
        q = self._separate(self.q_proj(q))
        k = self._separate(self.k_proj(k))
        v = self._separate(self.v_proj(v))
        attn = torch.softmax((q @ k.permute(0, 1, 3, 2)) / math.sqrt(q.shape[-1]), dim=-1)
        out = attn @ v
        b, nh, nt, cph = out.shape
        return self.out_proj(out.transpose(1, 2).reshape(b, nt, nh * cph))


class TwoWayAttentionBlock(nn.Module):
    def __init__(self, embedding_dim, num_heads, mlp_dim, skip_first_layer_pe):
        super().__init__()
        self.self_attn = Attention(embedding_dim, num_heads)
        self.norm1 = nn.LayerNorm(embedding_dim)
        self.cross_attn_token_to_image = Attention(embedding_dim, num_heads, 2)
        self.norm2 = nn.LayerNorm(embedding_dim)
        self.mlp = MLPBlock(embedding_dim, mlp_dim, nn.ReLU)
        self.norm3 = nn.LayerNorm(embedding_dim)
        self.norm4 = nn.LayerNorm(embedding_dim)
        self.cross_attn_image_to_token = Attention(embedding_dim, num_heads, 2)
        self.skip_first_layer_pe = skip_first_layer_pe

    def forward(self, queries, keys, query_pe, key_pe):
        if self.skip_first_layer_pe:
            queries = self.self_attn(queries, queries, queries)
        else:
            q = queries + query_pe
            queries = queries + self.self_attn(q, q, queries)
        queries = self.norm1(queries)
        q = queries + query_pe
        k = keys + key_pe
        queries = self.norm2(queries + self.cross_attn_token_to_image(q, k, keys))
        queries = self.norm3(queries + self.mlp(queries))
        q = queries + query_pe
        k = keys + key_pe
        keys = self.norm4(keys + self.cross_attn_image_to_token(k, q, queries))
        return queries, keys


class TwoWayTransformer(nn.Module):
    def __init__(self, depth=2, embedding_dim=PROMPT_DIM, num_heads=8, mlp_dim=2048):
        super().__init__()
        self.layers = nn.ModuleList(
            [TwoWayAttentionBlock(embedding_dim, num_heads, mlp_dim, i == 0) for i in range(depth)]
        )
        self.final_attn_token_to_image = Attention(embedding_dim, num_heads, 2)
        self.norm_final_attn = nn.LayerNorm(embedding_dim)

    def forward(self, image_embedding, image_pe, point_embedding):
        keys = image_embedding.flatten(2).permute(0, 2, 1)
        image_pe = image_pe.flatten(2).permute(0, 2, 1)
        queries = point_embedding
        for layer in self.layers:
            queries, keys = layer(queries, keys, point_embedding, image_pe)
        q = queries + point_embedding
        k = keys + image_pe
        queries = self.norm_final_attn(queries + self.final_attn_token_to_image(q, k, keys))
        return queries, keys


class MLP(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim, num_layers):
        super().__init__()
        h = [hidden_dim] * (num_layers - 1)
        self.layers = nn.ModuleList(nn.Linear(n, k) for n, k in zip([input_dim] + h, h + [output_dim]))
        self.num_layers = num_layers

    def forward(self, x):
        for i, layer in enumerate(self.layers):
            x = F.relu(layer(x)) if i < self.num_layers - 1 else layer(x)
        return x


class MaskDecoder(nn.Module):
    def __init__(self):
        super().__init__()
        dim = PROMPT_DIM
        self.transformer = TwoWayTransformer()
        self.iou_token = nn.Embedding(1, dim)
        self.num_mask_tokens = 4
        self.mask_tokens = nn.Embedding(self.num_mask_tokens, dim)
        self.output_upscaling = nn.Sequential(
            nn.ConvTranspose2d(dim, dim // 4, kernel_size=2, stride=2),
            LayerNorm2d(dim // 4),
            nn.GELU(),
            nn.ConvTranspose2d(dim // 4, dim // 8, kernel_size=2, stride=2),
            nn.GELU(),
        )
        self.output_hypernetworks_mlps = nn.ModuleList([MLP(dim, dim, dim // 8, 3) for _ in range(self.num_mask_tokens)])
        self.iou_prediction_head = MLP(dim, 256, self.num_mask_tokens, 3)

    def forward(self, image_embeddings, image_pe, sparse, dense):
        tokens = torch.cat([self.iou_token.weight, self.mask_tokens.weight], dim=0)
        tokens = tokens.unsqueeze(0).expand(sparse.size(0), -1, -1)
        tokens = torch.cat((tokens, sparse), dim=1)
        src = image_embeddings.expand(tokens.shape[0], -1, -1, -1) + dense
        pos_src = image_pe.expand(tokens.shape[0], -1, -1, -1)
        b, c, h, w = src.shape
        hs, src = self.transformer(src, pos_src, tokens)
        iou_token_out = hs[:, 0, :]
        mask_token_out = hs[:, 1, :]
        upscaled = self.output_upscaling(src.transpose(1, 2).reshape(b, c, h, w))
        hyper = self.output_hypernetworks_mlps[0](mask_token_out)[:, None, :]
        b, c, h, w = upscaled.shape
        masks = (hyper @ upscaled.view(b, c, h * w)).view(b, 1, h, w)
        iou = self.iou_prediction_head(iou_token_out)[:, :1]
        return masks, iou


class SafireModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.image_encoder = AdaptorImageEncoder()
        self.prompt_encoder = PromptEncoder()
        self.mask_decoder = MaskDecoder()
        self.register_buffer("pixel_mean", torch.tensor(PIXEL_MEAN).view(-1, 1, 1), False)
        self.register_buffer("pixel_std", torch.tensor(PIXEL_STD).view(-1, 1, 1), False)

    def encode(self, image_1024):
        x = (image_1024 - self.pixel_mean) / self.pixel_std
        return self.image_encoder(x.float())

    def decode_points(self, features, points):
        labels = torch.ones(points.shape[0], 1)
        sparse, dense = self.prompt_encoder(points[:, None, :], labels)
        return self.mask_decoder(features, self.prompt_encoder.get_dense_pe(), sparse, dense)
