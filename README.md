# ASUS ProArt PX13 — Fedora internal speakers fix

Fedora package that restores the built-in speakers on an ASUS ProArt PX13
(HN7306, AMD Ryzen AI Max+ / Strix Halo) running Fedora.

This work is based on [ftoleedo/px13-audio-fix](https://github.com/ftoleedo/px13-audio-fix).
The Fedora package is maintained by **devcoons**.

Tested on:

| Component     | Version                         |
|---------------|---------------------------------|
| Fedora        | 44                              |
| Kernel        | 7.1.10-200.fc44.x86_64          |
| kernel-devel  | 7.1.10-200.fc44.x86_64          |
| linux-firmware| 20260810-1.fc44                 |
| PipeWire      | 1.6.8                           |
| WirePlumber   | 0.5.14                          |
| ALSA          | 1.2.16.1                        |
| Secure Boot   | disabled                        |

Detected machine in that setup:

`ASUSTeKCOMPUTERINC.-ProArtPX13HN7306EA-1.0-HN7306EA`

## The problem

Headphones/headset worked. The AMD SoundWire ALSA card and the TAS2783
speaker amplifiers were present, but the built-in speaker sink was missing
from PipeWire. Kernel logs showed TAS2783 firmware/initialization failures
and repeated SoundWire `-22` parameter errors.

Audio topology:

```
AMD ACP / SoundWire
        |
        +-- RT721 ----------------> Headphones
        |
        +-- TAS2783 #1 -----------> Speaker Left
        |
        +-- TAS2783 #2 -----------> Speaker Right
```

Layers this package installs:

```
TAS2783 kernel driver  (DKMS)
        |
        v
ALSA UCM               (SKU-probed long-name override)
        |
        v
PipeWire / WirePlumber
        |
        v
Internal speakers
```

Two remaining bugs on stock kernels >= 7.1 (the TAS2783 driver landed in 7.1):

1. The machine driver does not tag the card with `spk:tas2783`, so ALSA UCM
   never creates a Speaker device.
2. Both amplifiers initialize with DSP cluster index `0x01`, so you get mono
   from one speaker (which one can change between boots).

Fedora's `linux-firmware` already ships the PX13 TAS2783 firmware as:

```
/usr/lib/firmware/ti/audio/tas2783/1714-1-0x8.bin.xz
/usr/lib/firmware/ti/audio/tas2783/1714-1-0xB.bin.xz
```

The stock kernel driver used to request `1714-1-8.bin` / `1714-1-B.bin`.
Temporary aliases were tested during diagnosis; they did **not** fix
initialization. Do **not** delete the Fedora `0x8` / `0xB` firmware files.
This package only removes leftover aliases at the firmware root, if present.

The complete fix is the PX13-specific DKMS module plus UCM, not firmware
symlinks.

## Fedora-specific DKMS change

The upstream DKMS configuration requests `LLVM=1`. Fedora's kernel is
GCC-built, and building the external module with Clang fails with errors
such as:

```
clang: error: unknown argument: '-mpreferred-stack-boundary=3'
clang: error: unknown argument: '-mindirect-branch=thunk-extern'
clang: error: unsupported option '-mrecord-mcount'
```

The module Makefile does not require LLVM. This package removes `LLVM=1`
from `module/dkms.conf` so DKMS uses the normal GCC/Kbuild toolchain, and
installs the module under `/lib/modules/$(uname -r)/extra/`.

## Requirements

- Fedora with kernel **>= 7.1**
- **Secure Boot disabled**, or the DKMS module signed and enrolled
- Matching `kernel-devel` (pulled by `kernel-devel-matched`)
- `linux-firmware` containing the TAS2783 `0x8` / `0xB` blobs

## Install the RPM

Build on the PX13 (or any x86_64 Fedora 44+ system):

```bash
sudo make install-deps
make rpm
sudo dnf install ./px13-audio-fix-*.noarch.rpm
sudo reboot
```

Or install a prebuilt package the same way with `dnf`.

Do **not** wrap the install in a second `sudo` layer beyond `dnf`. The
package's `%post` already runs as root. PipeWire profile selection happens
after reboot in your desktop session.

The package:

1. Registers the DKMS module (`snd-soc-tas2783-sdw-px13` 1.0)
2. Installs ALSA UCM speaker/codec fragments
3. Probes this machine's SoundWire `CardLongName` and writes the override
4. Enables a boot oneshot so the override is re-applied after SKU/DMI
   detection is available

It may not be able to replace the stock `snd-soc-tas2783-sdw` module while
it is loaded. That is expected. Reboot.

### Optional resume recovery

Do **not** install this unless suspend/resume actually breaks speakers.

First test: boot → speakers work → suspend → resume → speakers work.

Only if they die after resume:

```bash
sudo dnf install px13-audio-fix-resume
```

Recovery log: `/var/log/px13-soundwire-resume.log`

Manual recovery:

```bash
sudo /usr/libexec/px13-audio-fix/px13-soundwire-recover
```

## Verification after reboot

### 1. Patched kernel module

```bash
modinfo snd_soc_tas2783_sdw | grep '^filename:'
```

Expected:

```
filename: /lib/modules/$(uname -r)/extra/snd-soc-tas2783-sdw.ko.xz
```

The important part is `/extra/`, not the stock

`/kernel/sound/soc/codecs/snd-soc-tas2783-sdw.ko.xz`.

### 2. ALSA

```bash
cat /proc/asound/cards
```

Expected to include `amdsoundwire` and a long name containing `ProArtPX13`.

```bash
C=$(awk '/soundwire/ && /^ *[0-9]+ \[/ {print $1; exit}' /proc/asound/cards)
alsaucm -c "$C" list _devices/HiFi | grep Speaker
```

Must print `Speaker`.

### 3. PipeWire

```bash
wpctl status
```

Expected sinks:

- `Audio Coprocessor Speaker` (the important one)
- `Audio Coprocessor Headphones`

### 4. Playback

Use PipeWire directly:

```bash
pw-play /usr/share/sounds/alsa/Front_Left.wav
pw-play /usr/share/sounds/alsa/Front_Right.wav
```

Do **not** use `speaker-test -D pulse` as the primary test if ALSA reports
`Unknown PCM pulse`. That only means the ALSA pulse plugin is not present.
It does not mean the speaker driver is broken.

### 5. Kernel errors that should be gone

```bash
sudo journalctl -k -b | grep -Ei 'tas2783|soundwire|1714-1|firmware'
```

Previously:

```
Direct firmware load for 1714-1-8.bin failed
Direct firmware load for 1714-1-B.bin failed
error playback without fw download
Program transport params failed: -22
Program params failed: -22
```

Those should no longer appear during normal initialization.

## Kernel updates

DKMS is configured with `AUTOINSTALL="yes"`. After a Fedora kernel update:

```bash
dkms status
modinfo snd_soc_tas2783_sdw | grep '^filename:'
```

The module should still appear under `/lib/modules/<kernel>/extra/`.

If a future kernel breaks the build:

```bash
dkms status
sudo cat /var/lib/dkms/snd-soc-tas2783-sdw-px13/1.0/build/make.log
```

Do not copy `.ko` files between kernel versions.

Re-apply the UCM override after unusual hardware probing issues:

```bash
sudo px13-audio-fix-apply
```

## Uninstall

```bash
sudo dnf remove px13-audio-fix
```

That removes the DKMS registration and generated UCM overrides. The stock
in-tree module under `/kernel/sound/soc/codecs/` is left in place (this
package shadows it from `/extra/` rather than replacing it).

## Building

This repository is self-contained. The TAS2783 module, UCM files, and
helpers are vendored here (from [ftoleedo/px13-audio-fix](https://github.com/ftoleedo/px13-audio-fix)
commit `0de5121`). Nothing is fetched from GitHub at build time.

```bash
make rpm          # binary + source RPMs in the repo root
make srpm         # source RPM only
make clean
```

## Publishing to Copr

This repo is set up for Copr **SCM** builds (`make_srpm` via `.copr/Makefile`).
Copr clones GitHub and builds the SRPM from this tree; it does not download
anything else.

### 1. Push to GitHub

```bash
git push -u origin main
```

Repo: https://github.com/devcoons/px13-audio-fix

### 2. API token (once)

1. Open https://copr.fedorainfracloud.org/api/
2. Log in with your Copr/FAS account.
3. Save the snippet as `~/.config/copr`:

```ini
[copr-cli]
login = ...
username = YOUR_COPR_USER
token = ...
copr_url = https://copr.fedorainfracloud.org
```

```bash
sudo dnf install -y copr-cli
```

### 3. Create the project and package

Use **Fedora 44+** x86_64 (the package is `noarch`, but Copr still builds
it in an arch chroot). Add more chroots later if you want.

```bash
copr-cli create px13-audio-fix \
  --chroot fedora-44-x86_64 \
  --description "ASUS ProArt PX13 internal speaker fix (TAS2783 DKMS + ALSA UCM)" \
  --instructions "sudo dnf copr enable YOUR_COPR_USER/px13-audio-fix && sudo dnf install px13-audio-fix && sudo reboot"

copr-cli add-package-scm px13-audio-fix \
  --name px13-audio-fix \
  --clone-url https://github.com/devcoons/px13-audio-fix.git \
  --committish main \
  --spec px13-audio-fix.spec \
  --srpm-build-method make_srpm \
  --webhook-rebuild on

copr-cli build-package px13-audio-fix --name px13-audio-fix
```

`--srpm-build-method make_srpm` is required. The default `rpkg` method will
not produce `Source0` (`px13-audio-fix-1.0.tar.gz`).

### 4. Optional: rebuild on every git push

In Copr: project **Settings → Integrations**, copy the GitHub webhook URL.

In GitHub: repo **Settings → Webhooks → Add webhook**:

- Payload URL: the Copr URL
- Content type: `application/json`
- Events: **Just the push event**

### 5. Users install with

```bash
sudo dnf copr enable YOUR_COPR_USER/px13-audio-fix
sudo dnf install px13-audio-fix
sudo reboot
```

Web UI alternative: https://copr.fedorainfracloud.org → **New Project** →
**Packages → New Package → SCM** → clone URL above, spec
`px13-audio-fix.spec`, SRPM method **make_srpm**.

## Repository layout

| Path | Role |
|------|------|
| `module/` | TAS2783 DKMS source (GCC/`/extra`, no `LLVM=1`) |
| `configs/` | ALSA UCM speaker/codec fragments and long-name template |
| `lib/px13-detect.sh` | Runtime SKU/card probes |
| `fedora/` | apply-ucm helper, systemd unit, preset, udev rule |
| `50-px13-soundwire` | Optional s2idle hook (`px13-audio-fix-resume`) |
| `px13-soundwire-recover.sh` | Optional resume recovery script |
| `px13-audio-fix.spec` | Fedora RPM spec |

## Package layout

| Path | Purpose |
|------|---------|
| `/usr/src/snd-soc-tas2783-sdw-px13-1.0/` | DKMS module source |
| `/usr/share/alsa/ucm2/sof-soundwire/tas2783.conf` | Speaker device + L/R channel assignment |
| `/usr/share/alsa/ucm2/codecs/tas2783/init.conf` | Mixer remap |
| `/usr/share/px13-audio-fix/` | Detect helper + UCM template |
| `/usr/libexec/px13-audio-fix/apply-ucm` | Writes the SKU-specific UCM override |
| `/usr/lib/systemd/system/px13-audio-fix-ucm.service` | Applies UCM at boot |
| `/etc/px13-audio-fix.conf` | Cached ACP PCI / card long name |

The UCM long-name file cannot be shipped as a static RPM path: ALSA loads
`conf.d/${CardDriver}/${CardLongName}.conf` and `CardLongName` is built from
DMI (HN7306EA vs HN7306EAC, …). An override under the wrong name is never
read. The apply script probes the live card instead of hardcoding a SKU.

## Credits

- **ftoleedo** — [px13-audio-fix](https://github.com/ftoleedo/px13-audio-fix),
  the durable DKMS + UCM fix this package is based on
- **nealstar** — original 16-patch series, including the channel-selection
  control the DKMS module carries
- **fecet** — CachyOS packaging for the < 7.1 era
- **TI / Niranjan H Y, Baojun Xu, Kevin Lu** — upstream tas2783 driver
- **jamescutts, dmicheel, DevGrishin** — SKU / UCM long-name silent failure
- **devcoons** — Fedora packaging (GCC DKMS, RPM, FHS paths)

## License

Kernel module: GPL-2.0-only. Packaging and helper scripts: CC0-1.0.
See `LICENSE`.
