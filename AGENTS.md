# Working efficiently

- Read `ROADMAP.md` when resuming work. It records the agreed objective, ordered
  milestones and latest handoff. Keep it current when a milestone or blocker
  changes; consult local `CURRENT-STATE.md` for detailed device evidence.

- Preserve the user's full objective, but distinguish software work from hardware
  verification. Never claim an untested battery behavior is complete.
- Do useful independent implementation work while bounded phone-side jobs run.
  Do not create filler edits or redundant tests just to appear busy.
- Do not repeatedly poll charging, compilation, or backups. The user monitors long
  runs. Check at an expected milestone, reported completion/fault, or explicit request.
- A running autonomous job is not a reason for repeated status-only agent turns.
  If the next step only needs elapsed time, explain that once and give the monitoring
  command. Do not start a token-consuming sleep/poll loop.
- For persistent goals, follow the governing goal lifecycle rules. Do not falsely
  mark completion or blockage, and do not pause without the user's request. Explain
  when pausing automatic goal continuations would avoid paying for idle turns.
- Batch independent reads and searches; return only relevant output. Avoid repeatedly
  printing long history, unchanged status files, or the same documentation.
- Keep updates concise and milestone-oriented. Ask only necessary physical actions
  or missing information. Do not repeatedly ask whether the user is present/cool.
- Before restarting a job, verify its actual process/handle is terminal or missing.
  A console timeout is not proof it stopped. Never blindly replay hardware mutations.
- Use one USB client at a time; briefly pause conflicting watchers and restore them.
- Preserve encrypted root/home, recovery images, backups, and private credentials.
  Never print, embed in firmware, or commit secrets.
- The user authorizes automatic development unlock using the existing private
  local key whenever needed. Do not ask them to type the passphrase. Transfer
  credentials privately and remove the temporary phone-side key after unlock;
  never embed it in boot images or bypass encryption.
- Keep watchdog, current/voltage limits, and fault shutdown. Hardware validation
  gates must not be bypassed to save time. Do not raise charge limits without evidence.
- Make local commits for substantive completed work. Do not push unless requested.
