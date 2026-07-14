---
asset: dashboard.md
project: {{ project }}
root: {{ root }}
manifesto: {{ manifesto }}
canonical: {{ canonical }}
license: GPL 3
share_policy: "internal (internal, public, private, nda, secret)"
url: {{ url }}
started: {{ started }}
config: .pocket/config.md
status: .pocket/status.md
status_timestamp: "automatically generated"
inbox: inbox.md
inbox_timestamp: "automatically generated"
decisions: .pocket/decisions.md
stream: .pocket/stream.md
---

## Central

**ChatGPT**: {{ chatgpt_url }}

**Local**: [{{ local_path }}](<copy:{{ local_path }}>)

**Website**: {{ url }}

{% if repo_url %}
**GitHub**: {{ repo_url }}
{% endif %}

{% if local_repo %}
**Local Repo**: [{{ local_repo }}](<copy:{{ local_repo }}>)
{% endif %}

{% if custom_1_title or custom_1_content %}
**{{ custom_1_title }}**: {{ custom_1_content }}
{% endif %}

{% if custom_2_title or custom_2_content %}
**{{ custom_2_title }}**: {{ custom_2_content }}
{% endif %}

{% if custom_3_title or custom_3_content %}
**{{ custom_3_title }}**: {{ custom_3_content }}
{% endif %}

## Status
print $root/.pocket/status.md on screen

## Todo
print $somewhere/todista/whatdidido.md on screen

## Last three files
print head 20 lines of the three latest ***accessed*** files. <= If I have a file opened but not saved, the timestamp should be *now*
