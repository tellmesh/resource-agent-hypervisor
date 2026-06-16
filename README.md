# resource-agent-hypervisor

TellMesh meta-agent runtime — `ResourceRuntimeClient`, agent lifecycle helpers, and hypervisor integration layer.

Depends on [`hypervisor`](../hypervisor). Monorepo umbrella: [`../tellmesh/`](../tellmesh/).

```text
resource-agent-hypervisor -> runtime client + meta-agent glue
hypervisor                  -> deployments, contracts, CLI
tellmesh/agents/generated   -> thin HTTP agents using runtime_client
```

## Install

```bash
uv sync
pytest tests/ -q
```

## Usage

Generated agents import `runtime_client.client.ResourceRuntimeClient` to call the resource runtime (`RESOURCE_RUNTIME_URL`, default `http://localhost:8000`).

```bash
hypervisor run-agent weather-map-agent.local --detach --wait-healthy
curl -s http://localhost:8101/health
hypervisor describe-agent weather-map-agent.local
```

Audit examples vs deployments:

```bash
cd ../tellmesh
PYTHONPATH="../hypervisor:../uri3:." \
  python ../resource-agent-hypervisor/scripts/examples/audit_agent_reports.py
```

## Links

- [TODO](TODO.md)
- [hypervisor](../hypervisor)
- [resource-agent-factory](../resource-agent-factory)
- Org status: [`../TODO_STATUS.md`](../TODO_STATUS.md)

## License

Licensed under Apache-2.0.
