import builtins
import traceback
import unreal
import verify_saved
batch=builtins.PUSS_MOCAP_BATCH
cls=type(batch)
assert batch.running
if not hasattr(cls,'_unverified_complete_job'):
    cls._unverified_complete_job=cls.complete_job
    def complete_and_verify(self):
        job=self.job
        self._unverified_complete_job()
        try:
            report=verify_saved.verify(job,self.manifest)
            job['state']='verified'
            job['verified_utc']=report['verified_utc']
        except Exception:
            job['state']='failed'
            job['verification_error']=traceback.format_exc()
            unreal.log_error('MOCAP_READBACK_FAILED|'+job['stem']+'|'+job['verification_error'])
        self.write_status(force=True)
    cls.complete_job=complete_and_verify
unreal.log('MOCAP_VERIFIER_ATTACHED_SUCCESS|saved_packages_will_be_reloaded_per_take')
