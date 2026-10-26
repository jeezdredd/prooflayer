# Third-party code and weights in `analyzers/manipulation`

EXPERIMENTAL, not wired into the Tribunal roster. Everything here runs on CPU.

| part | origin | licence | what we did |
|---|---|---|---|
| `catnet_net.py` | CAT-Net v2, Kwon et al. (IJCV 2022), github.com/mjkwon2021/CAT-Net, built on HRNet (Microsoft, Ke Sun) | CAT-Net code Apache-2.0 and weights CC-BY 4.0 since the README licence update of 2026-08-05 (commits `64bd5239b923`, `331b8059c3f5`); HRNet part MIT ("LICENSE of HRNet" in the repo) | clean re-typed port for torch 2.x, CPU only, no `.cuda()`, config inlined; DCT coefficients estimated from the decoded luma (no `jpegio`) |
| `safire_net.py`, `safire.py` | SAFIRE, Kwon et al. (AAAI 2025), github.com/mjkwon2021/SAFIRE, built on Segment Anything (Meta) | SAFIRE code Apache-2.0 and weights CC-BY 4.0 since the README update of 2026-08-05 (commits `dd0f83aaedbc`, `ec2af6af8c78`); segment_anything Apache-2.0 | clean port of the adaptor ViT-B encoder, prompt encoder and mask decoder; deterministic k-means (farthest-point init) instead of random init; masks combined at 256 px before upscaling |
| `jpeg_grid.py` | ZERO, Nikoukhah et al., IPOL 2021 | re-implemented from the article only; the official C code, the Rust port and the photoholmes wrapper are AGPL-3.0 and were not used | numpy implementation of votes, global grid, foreign grid and missing grid (JPEG Q99 trick); region growing approximated on 3 px cells |
| `copymove.py` | Ehret, "Robust copy-move forgery detection by false alarms control", 2019 | re-implemented from the paper; the author's IPOL code is GPL-3.0 and was not used | OpenCV SIFT keypoints (Apache-2.0 since OpenCV 4.4), gradient-patch descriptors, a-contrario threshold, own grouping and dense verification |
| `ai_tiles.py` | Community Forensics ViT-S/16 (buildborderless/CommunityForensics-DeepfakeDet-ViT) | MIT | already shipped model, scored per 384 px tile |

## Weights used in the experiment

Files live outside git under `dataset/manipulation/weights/` (Google Drive links from the two READMEs,
downloaded without an account on 2026-10-26).

| file | sha256 | note |
|---|---|---|
| `CAT_full_v2.pth.tar` (original) | `f82aaafdd1142775231feedcea0bb7027f7370561d9e8d107465454001865989` | 915 MB with optimizer state |
| `catnet_v2_state.pt` (converted) | `60a3622cc7a77d82fb7d01bacaefa650bc617c0a8055372093da0c83b13a0dc2` | fp32 state dict only, loads with `weights_only=True` |
| `safire.pth` (original) | `65bdf6880380162d57f77d71b3fd367c3f16aebca316f942a821da16e9225b12` | 421 MB with optimizer state |
| `safire_state.pt` (converted) | `5ade61adb5edd26ed959258ed8a388358172a347302a7a51faa4ec973cfcf4b6` | fp32 state dict only |

## Attribution text for product credits (CC-BY 4.0 requires it)

- CAT-Net weights: M.-J. Kwon, S.-H. Nam, I.-J. Yu, H.-K. Lee, C. Kim, "Learning JPEG Compression Artifacts for Image Manipulation Detection and Localization", IJCV 2022. Weights CC-BY 4.0, code Apache-2.0.
- SAFIRE weights: M.-J. Kwon, W. Lee, S.-H. Nam, M. Son, C. Kim, "SAFIRE: Segment Any Forged Image Region", AAAI 2025. Weights CC-BY 4.0, code Apache-2.0.

## Open risk for the owner

Both learned models were trained on research-only datasets (CASIA v2, IMD2020, FantasticReality, tampCOCO).
The weight licence is explicit (CC-BY 4.0), but the author's README says users must check the rights of the
source images themselves. This provenance question is the owner's call before shipping.
