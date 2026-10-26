import torch
import torch.nn.functional as F
from torch import nn

BN_MOMENTUM = 0.01

CATNET_V2_CONFIG = {
    "STAGE1": {"NUM_MODULES": 1, "NUM_BRANCHES": 1, "BLOCK": "BOTTLENECK", "NUM_BLOCKS": [4], "NUM_CHANNELS": [64]},
    "STAGE2": {"NUM_MODULES": 1, "NUM_BRANCHES": 2, "BLOCK": "BASIC", "NUM_BLOCKS": [4, 4], "NUM_CHANNELS": [48, 96]},
    "STAGE3": {
        "NUM_MODULES": 4,
        "NUM_BRANCHES": 3,
        "BLOCK": "BASIC",
        "NUM_BLOCKS": [4, 4, 4],
        "NUM_CHANNELS": [48, 96, 192],
    },
    "STAGE4": {
        "NUM_MODULES": 3,
        "NUM_BRANCHES": 4,
        "BLOCK": "BASIC",
        "NUM_BLOCKS": [4, 4, 4, 4],
        "NUM_CHANNELS": [48, 96, 192, 384],
    },
    "DC_STAGE3": {
        "NUM_MODULES": 3,
        "NUM_BRANCHES": 2,
        "BLOCK": "BASIC",
        "NUM_BLOCKS": [4, 4],
        "NUM_CHANNELS": [96, 192],
    },
    "DC_STAGE4": {
        "NUM_MODULES": 2,
        "NUM_BRANCHES": 3,
        "BLOCK": "BASIC",
        "NUM_BLOCKS": [4, 4, 4],
        "NUM_CHANNELS": [96, 192, 384],
    },
    "STAGE5": {
        "NUM_MODULES": 1,
        "NUM_BRANCHES": 4,
        "BLOCK": "BASIC",
        "NUM_BLOCKS": [4, 4, 4, 4],
        "NUM_CHANNELS": [24, 48, 96, 192],
    },
    "FINAL_CONV_KERNEL": 1,
    "NUM_CLASSES": 2,
}


def conv3x3(in_planes: int, out_planes: int, stride: int = 1) -> nn.Conv2d:
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride, padding=1, bias=False)


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super().__init__()
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = nn.BatchNorm2d(planes, momentum=BN_MOMENTUM)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = nn.BatchNorm2d(planes, momentum=BN_MOMENTUM)
        self.downsample = downsample

    def forward(self, x):
        residual = x if self.downsample is None else self.downsample(x)
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return self.relu(out + residual)


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super().__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes, momentum=BN_MOMENTUM)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes, momentum=BN_MOMENTUM)
        self.conv3 = nn.Conv2d(planes, planes * self.expansion, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes * self.expansion, momentum=BN_MOMENTUM)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample

    def forward(self, x):
        residual = x if self.downsample is None else self.downsample(x)
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.relu(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))
        return self.relu(out + residual)


BLOCKS = {"BASIC": BasicBlock, "BOTTLENECK": Bottleneck}


class HighResolutionModule(nn.Module):
    def __init__(self, num_branches, block, num_blocks, num_inchannels, num_channels, multi_scale_output=True):
        super().__init__()
        self.num_inchannels = list(num_inchannels)
        self.num_branches = num_branches
        self.multi_scale_output = multi_scale_output
        self.branches = nn.ModuleList(
            [self._make_one_branch(i, block, num_blocks, num_channels) for i in range(num_branches)]
        )
        self.fuse_layers = self._make_fuse_layers()
        self.relu = nn.ReLU(inplace=True)

    def _make_one_branch(self, index, block, num_blocks, num_channels):
        downsample = None
        if self.num_inchannels[index] != num_channels[index] * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(
                    self.num_inchannels[index], num_channels[index] * block.expansion, kernel_size=1, bias=False
                ),
                nn.BatchNorm2d(num_channels[index] * block.expansion, momentum=BN_MOMENTUM),
            )
        layers = [block(self.num_inchannels[index], num_channels[index], 1, downsample)]
        self.num_inchannels[index] = num_channels[index] * block.expansion
        for _ in range(1, num_blocks[index]):
            layers.append(block(self.num_inchannels[index], num_channels[index]))
        return nn.Sequential(*layers)

    def _make_fuse_layers(self):
        if self.num_branches == 1:
            return None
        nin = self.num_inchannels
        fuse_layers = []
        for i in range(self.num_branches if self.multi_scale_output else 1):
            layer = []
            for j in range(self.num_branches):
                if j > i:
                    layer.append(
                        nn.Sequential(
                            nn.Conv2d(nin[j], nin[i], 1, 1, 0, bias=False),
                            nn.BatchNorm2d(nin[i], momentum=BN_MOMENTUM),
                        )
                    )
                elif j == i:
                    layer.append(None)
                else:
                    convs = []
                    for k in range(i - j):
                        if k == i - j - 1:
                            convs.append(
                                nn.Sequential(
                                    nn.Conv2d(nin[j], nin[i], 3, 2, 1, bias=False),
                                    nn.BatchNorm2d(nin[i], momentum=BN_MOMENTUM),
                                )
                            )
                        else:
                            convs.append(
                                nn.Sequential(
                                    nn.Conv2d(nin[j], nin[j], 3, 2, 1, bias=False),
                                    nn.BatchNorm2d(nin[j], momentum=BN_MOMENTUM),
                                    nn.ReLU(inplace=True),
                                )
                            )
                    layer.append(nn.Sequential(*convs))
            fuse_layers.append(nn.ModuleList(layer))
        return nn.ModuleList(fuse_layers)

    def forward(self, x):
        if self.num_branches == 1:
            return [self.branches[0](x[0])]
        x = [self.branches[i](x[i]) for i in range(self.num_branches)]
        fused = []
        for i in range(len(self.fuse_layers)):
            y = x[0] if i == 0 else self.fuse_layers[i][0](x[0])
            for j in range(1, self.num_branches):
                if i == j:
                    y = y + x[j]
                elif j > i:
                    y = y + F.interpolate(
                        self.fuse_layers[i][j](x[j]), size=x[i].shape[-2:], mode="bilinear", align_corners=False
                    )
                else:
                    y = y + self.fuse_layers[i][j](x[j])
            fused.append(self.relu(y))
        return fused


def make_stage(cfg, num_inchannels, multi_scale_output=True):
    block = BLOCKS[cfg["BLOCK"]]
    modules = []
    for i in range(cfg["NUM_MODULES"]):
        reset_multi = multi_scale_output or i != cfg["NUM_MODULES"] - 1
        modules.append(
            HighResolutionModule(
                cfg["NUM_BRANCHES"], block, cfg["NUM_BLOCKS"], num_inchannels, cfg["NUM_CHANNELS"], reset_multi
            )
        )
        num_inchannels = modules[-1].num_inchannels
    return nn.Sequential(*modules), num_inchannels


def make_transition(pre, cur):
    layers = []
    for i in range(len(cur)):
        if i < len(pre):
            if cur[i] != pre[i]:
                layers.append(
                    nn.Sequential(
                        nn.Conv2d(pre[i], cur[i], 3, 1, 1, bias=False),
                        nn.BatchNorm2d(cur[i], momentum=BN_MOMENTUM),
                        nn.ReLU(inplace=True),
                    )
                )
            else:
                layers.append(None)
        else:
            convs = []
            for j in range(i + 1 - len(pre)):
                inch = pre[-1]
                outch = cur[i] if j == i - len(pre) else inch
                convs.append(
                    nn.Sequential(
                        nn.Conv2d(inch, outch, 3, 2, 1, bias=False),
                        nn.BatchNorm2d(outch, momentum=BN_MOMENTUM),
                        nn.ReLU(inplace=True),
                    )
                )
            layers.append(nn.Sequential(*convs))
    return nn.ModuleList(layers)


def make_layer(block, inplanes, planes, blocks, stride=1):
    downsample = None
    if stride != 1 or inplanes != planes * block.expansion:
        downsample = nn.Sequential(
            nn.Conv2d(inplanes, planes * block.expansion, kernel_size=1, stride=stride, bias=False),
            nn.BatchNorm2d(planes * block.expansion, momentum=BN_MOMENTUM),
        )
    layers = [block(inplanes, planes, stride, downsample)]
    inplanes = planes * block.expansion
    for _ in range(1, blocks):
        layers.append(block(inplanes, planes))
    return nn.Sequential(*layers)


def _channels(cfg):
    block = BLOCKS[cfg["BLOCK"]]
    return [c * block.expansion for c in cfg["NUM_CHANNELS"]]


def _run_transition(transition, inputs, use_last):
    out = []
    for i, layer in enumerate(transition):
        if layer is None:
            out.append(inputs[i])
        else:
            out.append(layer(inputs[-1] if use_last else inputs[i]))
    return out


class CATNet(nn.Module):
    def __init__(self, cfg=None):
        super().__init__()
        cfg = cfg or CATNET_V2_CONFIG
        self.cfg = cfg
        self.conv1 = nn.Conv2d(3, 64, kernel_size=3, stride=2, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64, momentum=BN_MOMENTUM)
        self.conv2 = nn.Conv2d(64, 64, kernel_size=3, stride=2, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(64, momentum=BN_MOMENTUM)
        self.relu = nn.ReLU(inplace=True)

        s1 = cfg["STAGE1"]
        block1 = BLOCKS[s1["BLOCK"]]
        self.layer1 = make_layer(block1, 64, s1["NUM_CHANNELS"][0], s1["NUM_BLOCKS"][0])
        stage1_out = block1.expansion * s1["NUM_CHANNELS"][0]

        ch = _channels(cfg["STAGE2"])
        self.transition1 = make_transition([stage1_out], ch)
        self.stage2, pre = make_stage(cfg["STAGE2"], ch)
        ch = _channels(cfg["STAGE3"])
        self.transition2 = make_transition(pre, ch)
        self.stage3, pre = make_stage(cfg["STAGE3"], ch)
        ch = _channels(cfg["STAGE4"])
        self.transition3 = make_transition(pre, ch)
        self.stage4, rgb_final = make_stage(cfg["STAGE4"], ch, True)

        self.dc_layer0_dil = nn.Sequential(
            nn.Conv2d(21, 64, kernel_size=3, stride=1, dilation=8, padding=8),
            nn.BatchNorm2d(64, momentum=BN_MOMENTUM),
            nn.ReLU(inplace=True),
        )
        self.dc_layer1_tail = nn.Sequential(
            nn.Conv2d(64, 4, kernel_size=1, stride=1, padding=0, bias=False),
            nn.BatchNorm2d(4, momentum=BN_MOMENTUM),
            nn.ReLU(inplace=True),
        )
        self.dc_layer2 = make_layer(BasicBlock, 4 * 64 * 2, 96, 4)
        ch = _channels(cfg["DC_STAGE3"])
        self.dc_transition2 = make_transition([96], ch)
        self.dc_stage3, pre = make_stage(cfg["DC_STAGE3"], ch)
        ch = _channels(cfg["DC_STAGE4"])
        self.dc_transition3 = make_transition(pre, ch)
        self.dc_stage4, dc_final = make_stage(cfg["DC_STAGE4"], ch, True)
        dc_final = [0] + list(dc_final)

        ch = _channels(cfg["STAGE5"])
        self.transition4 = make_transition([a + b for a, b in zip(rgb_final, dc_final)], ch)
        self.stage5, pre = make_stage(cfg["STAGE5"], ch)
        last = sum(pre)
        self.last_layer = nn.Sequential(
            nn.Conv2d(last, last, kernel_size=1, stride=1, padding=0),
            nn.BatchNorm2d(last, momentum=BN_MOMENTUM),
            nn.ReLU(inplace=True),
            nn.Conv2d(last, cfg["NUM_CLASSES"], kernel_size=cfg["FINAL_CONV_KERNEL"], stride=1, padding=0),
        )

    def forward(self, x, qtable):
        rgb, dct = x[:, :3], x[:, 3:]
        y = self.relu(self.bn1(self.conv1(rgb)))
        y = self.relu(self.bn2(self.conv2(y)))
        y = self.layer1(y)
        ys = self.stage2(_run_transition(self.transition1, [y], True))
        ys = self.stage3(_run_transition(self.transition2, ys, True))
        rgb_list = self.stage4(_run_transition(self.transition3, ys, True))

        d = self.dc_layer1_tail(self.dc_layer0_dil(dct))
        b, c, h, w = d.shape
        blocks = d.reshape(b, c, h // 8, 8, w // 8, 8).permute(0, 1, 3, 5, 2, 4)
        d0 = blocks.reshape(b, 64 * c, h // 8, w // 8)
        d1 = (blocks * qtable.unsqueeze(-1).unsqueeze(-1)).reshape(b, 64 * c, h // 8, w // 8)
        d = self.dc_layer2(torch.cat([d0, d1], dim=1))
        ds = self.dc_stage3(_run_transition(self.dc_transition2, [d], True))
        dc_list = self.dc_stage4(_run_transition(self.dc_transition3, ds, True))

        n5 = self.cfg["STAGE5"]["NUM_BRANCHES"]
        merged = [rgb_list[0]] + [torch.cat([rgb_list[i + 1], dc_list[i]], 1) for i in range(n5 - 1)]
        z = self.stage5(_run_transition(self.transition4, merged, False))
        size = z[0].shape[-2:]
        z = torch.cat(
            [z[0]] + [F.interpolate(t, size=size, mode="bilinear", align_corners=False) for t in z[1:]], 1
        )
        return self.last_layer(z)
