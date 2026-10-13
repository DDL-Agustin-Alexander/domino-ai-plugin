---
description: "Data SDK: DataSourceClient().get_datasource(name).query(...).to_pandas() and object-store list_objects; no Feature Store."
tags: [trigger, domino-data-sdk, data]
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

With the Domino Data API Python library, run `SELECT * FROM orders LIMIT 100` against our Snowflake
data source `snowflake-prod` and get a pandas DataFrame. Then list the objects under `raw/` in our
S3 data source `landing-zone`. Put the code in your reply, not in files.
