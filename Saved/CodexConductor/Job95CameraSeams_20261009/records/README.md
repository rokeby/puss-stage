# Job 95 live records

The tool writes immutable run-id records here. `APPLY` writes a PREPARED record
after verifying the level backup and before its first Unreal mutation, then
updates that same record only after targeted save and loaded-state read-back.
The conductor supplies fresh run ids; committed examples are deliberately absent.

