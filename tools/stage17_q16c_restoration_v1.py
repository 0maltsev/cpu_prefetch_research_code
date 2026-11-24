"""D275 original D257 restoration proof with the explicit Q16c action identity."""
import re

def require(ok,message):
    if not ok:raise ValueError(message)

def restoration_status(receipt, *, attempt_id, request_sha256, authorization_sha256, expected_prestate):
    for name, expected in (("attempt_id", attempt_id), ("request_sha256", request_sha256),
                           ("authorization_sha256", authorization_sha256), ("action_id", "Q16c")):
        if receipt.get(name) != expected:
            raise ValueError("executor receipt binding differs: " + name)
    schema = receipt.get("schema_version")
    if schema == "cpu-prefetch-stage17-phase-action-failure/6":
        operation = receipt.get("quarantine_operation")
        if not isinstance(operation, dict) or type(operation.get("performed")) is not bool:
            raise ValueError("failure quarantine observation missing")
        quarantined = operation["performed"]
        readback = receipt.get("recovery_readback")
        expected_field = 'requested_hex'
        complete = False
    elif schema == "cpu-prefetch-stage17-phase-action-completion/6":
        quarantined = receipt.get("quarantined")
        if type(quarantined) is not bool:
            raise ValueError("completion quarantine observation missing")
        readback = receipt.get("live_restoration_readback")
        expected_field = 'expected_hex'
        complete = True
    else:
        raise ValueError("unsupported executor receipt schema")
    for field in ("leader_reaped", "process_group_gone", "restoration_verified"):
        if type(receipt.get(field)) is not bool:
            raise ValueError("missing actual restoration/cleanup observation: " + field)
    verified = (receipt["restoration_verified"] and not quarantined
                and receipt["leader_reaped"] and receipt["process_group_gone"])
    if verified:
        if not isinstance(readback, list) or not readback:
            raise ValueError("claimed restoration lacks actual readback")
        expected = {row["cpu"]: row["complete_value_hex"] for row in expected_prestate}
        require(set(expected) == {0, 1, 8}, "exact restoration CPU coverage required")
        seen = set()
        for row in readback:
            if (not isinstance(row, dict) or type(row.get("cpu")) is not int
                    or row["cpu"] < 0 or row["cpu"] in seen or row.get("matches") is not True
                    or not isinstance(row.get(expected_field), str)
                    or re.fullmatch(r"[0-9a-f]{16}", row[expected_field]) is None
                    or row.get("observed_hex") != row[expected_field]):
                raise ValueError("invalid hardware restoration readback")
            require(expected.get(row["cpu"]) == row[expected_field], "restoration differs from signed prestate")
            seen.add(row["cpu"])
        require(seen == set(expected), "restoration omits CPUs")
    return {"hardware_restoration_verified": verified, "executor_completed": complete,
            "executor_quarantined": quarantined}
