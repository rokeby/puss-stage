import builtins
import datetime
import json
import pathlib
import unreal

batch = builtins.PUSS_MOCAP_BATCH
cls = type(batch)
if not hasattr(cls, '_json_write_status'):
    cls._json_write_status = cls.write_status


def write_report(self, force=False):
    before = self.last_write
    self._json_write_status(force)
    if before == self.last_write:
        return
    finished = all(j['state'] in ('verified', 'solved_exported', 'failed') for j in self.jobs)
    status = 'Running' if self.running else ('Queue finished' if finished else 'Stopped; attention required')
    lines = ['# Mocap batch — 10 September 2026', '', '**Status:** ' + status + '.',
             '', 'Updated: ' + datetime.datetime.now(datetime.timezone.utc).isoformat() + '.',
             '', 'Approved template: `/Game/Metahuman/Shore1`. The original short test is retained.',
             '', 'Output root: `' + self.manifest['root'] + '`.',
             '', '| Take | Full video frames | State | Frames with body data |',
             '| --- | ---: | --- | ---: |']
    for job in self.jobs:
        count = job.get('coverage', {}).get('body_frames', '—')
        lines.append('| ' + job['stem'] + ' | ' + str(job['image_count']) + ' | ' + job['state'] + ' | ' + str(count) + ' |')
    lines += ['', 'Each take gets a full-length Performance asset in `Performances` and a raw performer-skeleton Animation Sequence in `RawAnimations`.',
              '', '`verified` means the saved Performance and animation packages were reloaded from disk, the agreed solve settings matched, body-frame coverage survived reloading, all five processing stages completed, and the export has the full sample count with changing body poses.',
              '', 'Full-range Capture Data copies reference the same ingested images without the shorter audio tracks. The original ingests, audio, and source videos are retained.',
              '', 'The queue runs inside the open Unreal Editor. Leave Unreal open and the PC powered on; locking Windows is fine. It prevents automatic system sleep and temporarily disables Unreal background CPU throttling, then releases/restores both when the queue finishes.',
              '', 'Backup: `E:/PussStage/Backups/PreMocapFullBatch-20260910-173855`.',
              '', 'Detailed status: [batch_status.json](../Saved/CodexMocap/batch_status.json). Per-take read-back reports: `Saved/CodexMocap/Verification/`.']
    audit_path = pathlib.Path('E:/PussStage/Saved/CodexMocap/batch_final_audit.json')
    if not self.running and audit_path.exists():
        result = json.loads(audit_path.read_text(encoding='utf-8'))
        lines += ['', '**Final audit:** ' + ('Passed' if result.get('success') else 'Review required') + '.',
                  '', '[Final saved-state checks](../Saved/CodexMocap/batch_final_audit.json).']
        for issue in result.get('issues', []):
            lines.append('- ' + issue)
        if result.get('error'):
            lines += ['', 'The audit encountered an error; see the linked report.']
    lines += ['', 'Rendered review of the full takes, cleanup, final MetaHuman casting and scene placement remain separate steps.']
    pathlib.Path('E:/PussStage/Docs/MocapBatch-20260910.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


cls.write_status = write_report
batch.write_status(force=True)
unreal.log('MOCAP_BATCH_REPORT_ATTACHED|Docs/MocapBatch-20260910.md')
