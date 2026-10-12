# Configuration ownership

Use .env.example and app.core.config.Settings for the currently implemented knowledge/SQLite adapters. Add versioned retrieval/model/prompt settings when their adapters exist. Dataset records and secrets belong outside committed configuration; runtime data is stored under data/private/.

Skeleton only; no adapter/UI implementation is provided here.
