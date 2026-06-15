from hypervisor.evolution.models import load_proposal
from hypervisor.evolution.validator import validate_proposal


def test_evolution_proposal_validates():
    proposal = load_proposal("examples/08_evolution/proposals/add_orders_agent.yaml")
    assert proposal.proposal_id == "add-orders-agent"
    assert validate_proposal(proposal) == []
