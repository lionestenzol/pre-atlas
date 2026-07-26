# DropList Doctrine

Quote these at the top of every Execution Packet. They are the always-loaded preamble.

1. **The graph has authority.** Agents, tools, automations, and users can propose. The graph controls state.

2. **No node is done without evidence.** Tool runs produce receipts. Receipts are verified against the node's `done_condition`. A tool succeeding is not a node done.

3. **No tool action runs without a node.** The loop is the only path to a side effect.

4. **No dependency is removed without reason.** Dependencies in `depends_on` are load-bearing.

5. **No completed core is reopened unless validation fails.** The do-not-reopen lock is a runtime guard, not a comment.

6. **Do not optimize interface before proving state.** State first. Always.

---

These are the six lines. The Bible elaborates. See `BIBLE.md`.
