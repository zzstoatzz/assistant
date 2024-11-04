from prefect.cache_policies import INPUTS, CachePolicy

INPUTS_MINUS_AGENTS: CachePolicy = INPUTS - 'agents'
