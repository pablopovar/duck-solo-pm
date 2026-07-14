---
asset: config.md
project: {{ project }}
score: {{ score }}
root: {{ root }}
manifesto: {{ manifesto }}
canonical: {{ canonical }}
license: GPL 3
share_policy: "internal (internal, public, private, nda, secret)"
url: {{ url }}
chatgpt: {{ chatgpt_url }}
local: {{ local_path | tojson }}
repo: {{ repo_url | tojson }}
local_repo: {{ local_repo | tojson }}
custom_fields:
  - title: {{ custom_1_title | tojson }}
    content: {{ custom_1_content | tojson }}
  - title: {{ custom_2_title | tojson }}
    content: {{ custom_2_content | tojson }}
  - title: {{ custom_3_title | tojson }}
    content: {{ custom_3_content | tojson }}
started: {{ started }}
config: .pocket/config.md
status: .pocket/status.md
status_timestamp: "automatically generated"
inbox: inbox.md
inbox_timestamp: "automatically generated"
decisions: .pocket/decisions.md
stream: .pocket/stream.md
---

some_config: false-for-now
