"""
E2E tests for audit trail functionality.

Tests that audit logs are created across operations and can be queried.
"""


def test_audit_trail_for_trial_creation(graphql_client):
    """Test that trial creation is audited."""
    # Create a trial
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
                name
            }
        }
    """

    create_result = graphql_client(
        create_mutation,
        {"input": {"name": "Audited Trial", "phase": "Phase I"}}
    )
    trial_id = create_result["data"]["createTrial"]["id"]

    # Query audit logs for the trial
    audit_query = """
        query AuditLog($input: GetAuditLogInput!) {
            auditLog(input: $input) {
                entries {
                    action
                    entity
                    entityId
                    payloadJson
                    createdAt
                }
            }
        }
    """

    audit_result = graphql_client(
        audit_query,
        {"input": {"entity": "trial", "entityId": str(trial_id), "limit": 10}}
    )

    assert "errors" not in audit_result, f"GraphQL errors: {audit_result.get('errors')}"
    audit_logs = audit_result["data"]["auditLog"]["entries"]

    # Should have at least one audit log for create_trial
    assert len(audit_logs) >= 1
    create_log = next((log for log in audit_logs if log["action"] == "create_trial"), None)
    assert create_log is not None
    assert create_log["entity"] == "trial"
    assert create_log["entityId"] == str(trial_id)


def test_audit_trail_for_update(graphql_client):
    """Test that trial updates are audited with metadata."""
    # Create a trial
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
            }
        }
    """

    create_result = graphql_client(
        create_mutation,
        {"input": {"name": "Trial for Update", "phase": "Phase I"}}
    )
    trial_id = create_result["data"]["createTrial"]["id"]

    # Update the trial
    update_mutation = """
        mutation UpdateTrial($input: UpdateTrialMetadataInput!) {
            updateTrialMetadata(input: $input) {
                id
            }
        }
    """

    graphql_client(
        update_mutation,
        {"input": {"trialId": trial_id, "phase": "Phase II"}}
    )

    # Query audit logs
    audit_query = """
        query AuditLog($input: GetAuditLogInput!) {
            auditLog(input: $input) {
                entries {
                    action
                    entity
                    entityId
                    payloadJson
                }
            }
        }
    """

    audit_result = graphql_client(
        audit_query,
        {"input": {"entity": "trial", "entityId": str(trial_id), "limit": 20}}
    )

    audit_logs = audit_result["data"]["auditLog"]["entries"]

    # Should have both create and update logs
    actions = [log["action"] for log in audit_logs]
    assert "create_trial" in actions
    assert "update_trial_metadata" in actions

    # Update log should have metadata about changes
    update_log = next((log for log in audit_logs if log["action"] == "update_trial_metadata"), None)
    assert update_log is not None
    assert update_log["payloadJson"] is not None


def test_audit_trail_for_site_registration(graphql_client):
    """Test that site registration is audited."""
    # Create a trial
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
            }
        }
    """

    create_result = graphql_client(
        create_mutation,
        {"input": {"name": "Trial for Site", "phase": "Phase I"}}
    )
    trial_id = create_result["data"]["createTrial"]["id"]

    # Register a site
    register_mutation = """
        mutation RegisterSite($input: RegisterSiteToTrialInput!) {
            registerSiteToTrial(input: $input) {
                siteId
            }
        }
    """

    register_result = graphql_client(
        register_mutation,
        {"input": {"trialId": trial_id, "siteName": "Test Site", "country": "USA"}}
    )
    site_id = register_result["data"]["registerSiteToTrial"]["siteId"]

    # Query audit logs for trial_site (the entity type used by the audit decorator)
    audit_query = """
        query AuditLog($input: GetAuditLogInput!) {
            auditLog(input: $input) {
                entries {
                    action
                    entity
                    entityId
                }
            }
        }
    """

    audit_result = graphql_client(
        audit_query,
        {"input": {"entity": "trial_site", "entityId": f"{trial_id}_{site_id}", "limit": 10}}
    )

    audit_logs = audit_result["data"]["auditLog"]["entries"]

    # Should have audit log for site registration
    register_log = next((log for log in audit_logs if log["action"] == "register_site_to_trial"), None)
    assert register_log is not None
    assert register_log["entity"] == "trial_site"
    assert register_log["entityId"] == f"{trial_id}_{site_id}"


def test_audit_trail_ordering(graphql_client):
    """Test that audit logs are returned in reverse chronological order."""
    # Create a trial
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
            }
        }
    """

    create_result = graphql_client(
        create_mutation,
        {"input": {"name": "Trial for Ordering", "phase": "Phase I"}}
    )
    trial_id = create_result["data"]["createTrial"]["id"]

    # Perform multiple updates
    update_mutation = """
        mutation UpdateTrial($input: UpdateTrialMetadataInput!) {
            updateTrialMetadata(input: $input) {
                id
            }
        }
    """

    for i in range(3):
        graphql_client(
            update_mutation,
            {"input": {"trialId": trial_id, "name": f"Update {i}"}}
        )

    # Query audit logs
    audit_query = """
        query AuditLog($input: GetAuditLogInput!) {
            auditLog(input: $input) {
                entries {
                    action
                    createdAt
                }
            }
        }
    """

    audit_result = graphql_client(
        audit_query,
        {"input": {"entity": "trial", "entityId": str(trial_id), "limit": 10}}
    )

    audit_logs = audit_result["data"]["auditLog"]["entries"]
    assert len(audit_logs) >= 4  # 1 create + 3 updates

    # Verify logs are in reverse chronological order (most recent first)
    timestamps = [log["createdAt"] for log in audit_logs]
    assert timestamps == sorted(timestamps, reverse=True)


def test_audit_trail_limit(graphql_client):
    """Test that audit log limit parameter works."""
    # Create a trial
    create_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
            }
        }
    """

    create_result = graphql_client(
        create_mutation,
        {"input": {"name": "Trial for Limit", "phase": "Phase I"}}
    )
    trial_id = create_result["data"]["createTrial"]["id"]

    # Perform multiple updates
    update_mutation = """
        mutation UpdateTrial($input: UpdateTrialMetadataInput!) {
            updateTrialMetadata(input: $input) {
                id
            }
        }
    """

    for i in range(10):
        graphql_client(
            update_mutation,
            {"input": {"trialId": trial_id, "name": f"Update {i}"}}
        )

    # Query with limit
    audit_query = """
        query AuditLog($input: GetAuditLogInput!) {
            auditLog(input: $input) {
                entries {
                    action
                }
            }
        }
    """

    audit_result = graphql_client(
        audit_query,
        {"input": {"entity": "trial", "entityId": str(trial_id), "limit": 5}}
    )

    audit_logs = audit_result["data"]["auditLog"]["entries"]
    assert len(audit_logs) == 5  # Respects limit
