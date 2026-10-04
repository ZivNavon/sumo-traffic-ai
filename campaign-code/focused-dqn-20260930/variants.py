"""One-factor changes; applied only inside each isolated worker process."""
import inspect
_updates=[]
def diagnostics():
    global _updates
    values=_updates;_updates=[]
    if not values:return {}
    return {k:sum(v[k] for v in values)/len(values) for k in values[0]}
def install(task,td,ta,ai,ac,torch,np):
    v=task['variant']
    assert td.LR == .001 and td.EPS_DECAY == .997
    if v == 'lr0003': td.LR = .0003
    elif v == 'eps998': td.EPS_DECAY = .998
    if v in ('mask_pedestrians','mask_link'):
        indices=[15,16] if v=='mask_pedestrians' else [14]
        for module in (td,ta,ai,ac):
            if not hasattr(module,'state_to_vector'): continue
            original=module.state_to_vector
            def masked(*args,_original=original,**kwargs):
                result=_original(*args,**kwargs).copy();result[indices]=0;return result
            module.state_to_vector=masked
    elif v=='entropy005':ta.ENTROPY_COEF=.05
    elif v=='normalized_advantage':
        source=inspect.getsource(ta.update)
        needle='advantages = (returns - values.detach())'
        assert source.count(needle)==1
        source=source.replace(needle,needle+'\n        advantages = (advantages - advantages.mean()) / (advantages.std(unbiased=False) + 1e-8)')
        exec(compile(source,'normalized_advantage_update','exec'),ta.__dict__)
    if task['algorithm']=='dqn':
        source=inspect.getsource(td.DQNAgent.train_step)
        import textwrap
        source=textwrap.dedent(source)
        assert 'nn.functional.mse_loss(q_current, q_target)' in source,source
        if v=='huber':source=source.replace('nn.functional.mse_loss(q_current, q_target)','nn.functional.huber_loss(q_current, q_target, reduction="mean", delta=1.0)')
        source=source.replace('self.optimizer.step()', '_record_update(self, q_current, q_target, loss)\n    self.optimizer.step()')
        def record(agent,current,target,loss):
            with torch.no_grad():
                errors=(current-target).abs();norm=float(torch.sqrt(sum((x.grad**2).sum() for x in agent.online.parameters() if x.grad is not None)))
                _updates.append(dict(loss=float(loss),td_abs_mean=float(errors.mean()),td_abs_median=float(errors.median()),td_abs_p95=float(torch.quantile(errors,.95)),td_fraction_above_one=float((errors>1).float().mean()),gradient_norm_before_clip=norm,gradient_norm_after_clip=norm))
        scope=dict(td.__dict__,_record_update=record);exec(compile(source,'instrumented_dqn_update','exec'),scope)
        td.DQNAgent.train_step=scope['train_step']
