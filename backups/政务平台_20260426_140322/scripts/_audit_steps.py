import sys; sys.path.insert(0,'system')
from phase2_protocol_driver import get_steps_spec
for ent in ['4540','1151']:
    print(f'\n=== entType={ent} ({len(get_steps_spec(ent))} steps) ===')
    for num,name,fn,opt in get_steps_spec(ent):
        fn_name = fn.__name__ if fn else "?"
        print(f'  {num:2d} {name:60s}  fn={fn_name:40s}  opt={opt}')
