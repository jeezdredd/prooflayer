---
type: analyzer
created: 2026-05-31
updated: 2026-09-04
source: backend/analyzers/implementations/npr_detector.py
status: implemented, tested, not seeded
---

# NPR Detector

Neighboring Pixel Relationships (Tan et al., *Rethinking the Up-Sampling Operations in
CNN-based Generative Network for Generalizable Deepfake Detection*, CVPR 2024). Until
2026-09-04 this name was attached to `Wvolf/ViT_Deepfake_Detection`, a face-swap ViT with no
relation to NPR; that model now lives at [[face-deepfake-detector]].

> [!warning] Measured useless on diffusion output - not in the active roster
> On 60 flickr photos vs 60 diffusiondb images: **AUC 0.499**, `authentic` at p<0.01 on
> **58/60 AI images and 57/60 real ones**. The checkpoint is ProGAN-trained and the artifact it
> keys on (nearest-neighbour upsampling residue) is not what diffusion samplers leave behind.
> Because its logits saturate at ±100, it was also a *confident* wrong voter: it pushed 27/60
> AI images into `needs_review`. Removed from `seed_analyzers`, `preload_models` and the
> `eval_detectors` roster. The module stays because it is a correct, verified implementation of
> a GAN-era detector and can be re-seeded if that threat matters. See [[fixes/audit-2026-08]].

## What it actually is

The released checkpoint is **not** a ResNet-50. It is the ResNet-50 stem plus `layer1` and
`layer2` only, 1.44M parameters, 5.8 MB:

```
conv1 3x3/2 (3->64) -> bn -> relu -> maxpool 3x3/2
layer1: 3 x Bottleneck(64)   -> 256 ch
layer2: 4 x Bottleneck(128)  -> 512 ch, stride 2 on conv2
adaptive avgpool -> fc1 Linear(512, 1)
```

Input is the NPR residual, not the image:

```python
down = F.interpolate(x, scale_factor=0.5, mode="nearest", recompute_scale_factor=True)
up   = F.interpolate(down, scale_factor=2.0, mode="nearest", recompute_scale_factor=True)
npr  = x - up
logit = net(npr * 2.0 / 3.0)
p_fake = sigmoid(logit)
```

Preprocessing matches the authors' HF demo exactly: RGB, ImageNet mean/std, **no resize**
(the artifact is destroyed by resampling), odd dimensions truncated to even. Our only
addition is a centre crop to 1024 px on the long side, without resampling, to bound cost.

## Weights

- Source: `model_epoch_last_3090.pth` in the authors' GitHub repo, the checkpoint their HF
  demo loads. sha256 `b67a9155…` pinned in code; downloaded once into
  `$HF_HOME/prooflayer-npr/`, verified on every load, re-fetched if the cached file is
  corrupt. `NPR_WEIGHTS_PATH` overrides for air-gapped hosts.
- `torch.load(weights_only=True)` - the file is a plain state dict, no pickle execution.
- The repo declares no licence. Research code; fine for the diploma, flag before commercial use.
- torchvision is not a dependency, so `Bottleneck` is implemented locally.

## Verification

`strict=True` load of all 146 tensors succeeds against a fresh `NPRNet`. On the two images the
authors ship with their demo: `midjourney1.png` -> logit **+110.3** (fake),
`CelebAHQ_00000110.png` -> logit **-113.7** (real). Residual of a constant image is exactly 0,
of a 1-px checkerboard exactly 1. 24 unit tests cover the residual, truncation, checkpoint
layout, checksum enforcement and verdict bands.

## Verdict thresholds

Same bands as the other probabilistic detectors (0.85 / 0.65 / 0.35 / 0.15). In practice the
model is never in the middle band.

## Evidence shape

```json
{
  "model": "NPR ResNet (Tan et al., CVPR 2024)",
  "weights_sha256": "b67a91555ce7",
  "ai_probability": 0.0,
  "logit": -113.65,
  "input": {"width": 1024, "height": 1024, "analysed_width": 1024, "analysed_height": 1024, "cropped": false},
  "training_corpus": "ProGAN 4-class (CNNDetection); authors report 92.2% mean acc over 28 generators"
}
```

## See also

- [[face-deepfake-detector]] - the model that used to carry this name
- [[community-forensics]] - the detector that actually separates diffusion output (AUC 1.000 here)
- [[concepts/detector-evaluation]] - how the numbers above were produced
- [[concepts/detection-strategy-2026]] - where NPR was originally planned
