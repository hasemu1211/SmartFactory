# Temporary transfer: ROS2 Codex/OMX skills

This directory is a **temporary Git transfer bundle** for installing two local Codex/OMX skills on another machine, such as a notebook PC.

Included skills:

- `ros2-engineering-handbook` — cross-domain ROS2 engineering handbook/reference layer.
- `narrow-space-robot-navigation` — tight-clearance mobile robot navigation guidance skill.

Archive source provenance:

- `ros2-engineering-handbook` imports a curated subset of <https://github.com/dbwls99706/ros2-engineering-skills> at commit `3706f65`.
- The archive includes internal `INSTALL.md`, `MANIFEST.md`, provenance files, and upstream license text.

## Install on the notebook after `git pull`

From the SmartFactory repository root on the notebook:

```bash
cd tmp/ros2-mobile-robot-skills-transfer-20260703
sha256sum -c SHA256SUMS
./install_to_codex_skills.sh
```

Then restart the Codex/OMX session so skill discovery refreshes.

If the script cannot run, install manually:

```bash
cd tmp/ros2-mobile-robot-skills-transfer-20260703
sha256sum -c SHA256SUMS
rm -rf /tmp/ros2-mobile-robot-skills-install
mkdir -p /tmp/ros2-mobile-robot-skills-install
tar -xzf ros2-mobile-robot-skills-20260703.tar.gz -C /tmp/ros2-mobile-robot-skills-install
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -a /tmp/ros2-mobile-robot-skills-install/ros2-engineering-handbook "${CODEX_HOME:-$HOME/.codex}/skills/"
cp -a /tmp/ros2-mobile-robot-skills-install/narrow-space-robot-navigation "${CODEX_HOME:-$HOME/.codex}/skills/"
```

Optional validation, if the notebook has the system `skill-creator` skill installed:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" "${CODEX_HOME:-$HOME/.codex}/skills/ros2-engineering-handbook"
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" "${CODEX_HOME:-$HOME/.codex}/skills/narrow-space-robot-navigation"
```

## Remove this temporary transfer from the repository after install

After the notebook confirms the skills are installed, remove this temporary directory with a follow-up cleanup commit:

```bash
git rm -r tmp/ros2-mobile-robot-skills-transfer-20260703
git commit -m "Remove temporary ROS2 skills transfer bundle"
git push
```

This removes only the Git transfer copy. It does **not** remove the installed skills under `~/.codex/skills`.
