# Obsidian setup for a wikify wiki

The wiki directory works as an [Obsidian](https://obsidian.md/) vault out of
the box. Read this only when the user asks about Obsidian or wants to view
their wiki visually.

## Built-in compatibility

- `[[wikilinks]]` render as clickable links
- The Graph View visualizes the knowledge network — useful for spotting
  orphans and clusters that this skill's lint won't catch
- YAML frontmatter powers Dataview queries
- The `raw/assets/` folder holds images referenced via `![[image.png]]`

## Recommended Obsidian settings

- Set the attachment folder to `raw/assets/` (Settings → Files & Links → Default
  location for new attachments → "In subfolder under current folder" → `raw/assets`)
- Enable wikilinks (Settings → Files & Links → Use [[Wikilinks]]) — usually on
  by default
- Install the **Dataview** plugin for queries like:
  ```
  TABLE tags, updated FROM "entities" WHERE contains(tags, "company")
  ```
- Install the **Templater** plugin if the user wants to manually create new
  entity/concept pages from frontmatter templates

## Server-resident wikis: obsidian-headless

When the wiki lives on a server (e.g. a VPS where an agent ingests sources
from cron) and the user wants to browse it on a desktop or phone, use
[obsidian-headless](https://www.npmjs.com/package/obsidian-headless) — it
syncs vaults via Obsidian Sync without a GUI.

### Setup

```bash
# Requires Node.js 22+
npm install -g obsidian-headless

# Login (requires Obsidian account with Sync subscription)
ob login --email <email> --password '<password>'

# Create a remote vault for the wiki
ob sync-create-remote --name "LLM Wiki"

# Connect the wiki directory to the vault
cd ~/wiki
ob sync-setup --vault "<vault-id>"

# Initial sync
ob sync

# Continuous sync (foreground — use systemd for background)
ob sync --continuous
```

### Continuous background sync via systemd

```ini
# ~/.config/systemd/user/obsidian-wiki-sync.service
[Unit]
Description=Obsidian Wiki Sync
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/path/to/ob sync --continuous
WorkingDirectory=/home/user/wiki
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now obsidian-wiki-sync
sudo loginctl enable-linger $USER   # so sync survives logout
```

This lets the agent write to `~/wiki` on the server while the user browses
the same vault in Obsidian on a laptop or phone — changes appear within
seconds.

## When NOT to use Obsidian

If the user just wants the wiki and never plans to view it visually, skip
this entirely. The wiki is plain markdown — it works in any editor. Don't
suggest installing Obsidian unless the user asks for it.
