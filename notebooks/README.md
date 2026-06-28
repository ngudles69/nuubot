# notebooks

One notebook per object.

Each object notebook should contain:

- smoke checks for init/start/stop shape.
- functional checks for the object's own contract.
- unmarked cells for debugging only.

Use markers from `wiki/notebooks.md`:

```python
# nuubot: prod
# nuubot: smoke
```

No marker means scratch/debug and must not migrate.
