"""
E2E tests for site registration.

Tests the multi-table transaction that creates/links sites to trials.
"""


def test_register_site_to_trial(graphql_client):
    """Test registering a new site to a trial."""
    # First create a trial
    create_trial_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
                name
            }
        }
    """

    trial_result = graphql_client(
        create_trial_mutation,
        {"input": {"name": "Trial with Sites", "phase": "Phase II"}}
    )
    trial_id = trial_result["data"]["createTrial"]["id"]

    # Register a site to the trial
    register_mutation = """
        mutation RegisterSite($input: RegisterSiteToTrialInput!) {
            registerSiteToTrial(input: $input) {
                siteId
                siteName
                country
                trialId
                linkStatus
            }
        }
    """

    register_variables = {
        "input": {
            "trialId": trial_id,
            "siteName": "Mayo Clinic",
            "country": "USA"
        }
    }

    register_result = graphql_client(register_mutation, register_variables)
    assert "errors" not in register_result, f"GraphQL errors: {register_result.get('errors')}"
    assert register_result["data"]["registerSiteToTrial"]["siteName"] == "Mayo Clinic"
    assert register_result["data"]["registerSiteToTrial"]["country"] == "USA"
    assert register_result["data"]["registerSiteToTrial"]["trialId"] == trial_id
    assert register_result["data"]["registerSiteToTrial"]["linkStatus"] == "pending"

    site_id = register_result["data"]["registerSiteToTrial"]["siteId"]

    # Verify the site appears in trial details
    get_trial_query = """
        query GetTrial($id: Int!) {
            trial(id: $id) {
                id
                name
                sites {
                    id
                    name
                    country
                    linkStatus
                }
            }
        }
    """

    trial_details = graphql_client(get_trial_query, {"id": trial_id})
    assert "errors" not in trial_details, f"GraphQL errors: {trial_details.get('errors')}"
    sites = trial_details["data"]["trial"]["sites"]
    assert len(sites) == 1
    assert sites[0]["id"] == site_id
    assert sites[0]["name"] == "Mayo Clinic"
    assert sites[0]["country"] == "USA"
    assert sites[0]["linkStatus"] == "pending"


def test_register_existing_site_to_new_trial(graphql_client):
    """Test that existing sites can be linked to multiple trials."""
    # Create first trial and register a site
    create_trial_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
            }
        }
    """

    trial1_result = graphql_client(
        create_trial_mutation,
        {"input": {"name": "Trial 1", "phase": "Phase I"}}
    )
    trial1_id = trial1_result["data"]["createTrial"]["id"]

    register_mutation = """
        mutation RegisterSite($input: RegisterSiteToTrialInput!) {
            registerSiteToTrial(input: $input) {
                siteId
                siteName
            }
        }
    """

    site_result = graphql_client(
        register_mutation,
        {"input": {"trialId": trial1_id, "siteName": "Shared Site", "country": "UK"}}
    )
    site_id = site_result["data"]["registerSiteToTrial"]["siteId"]

    # Create second trial and register the same site
    trial2_result = graphql_client(
        create_trial_mutation,
        {"input": {"name": "Trial 2", "phase": "Phase II"}}
    )
    trial2_id = trial2_result["data"]["createTrial"]["id"]

    site2_result = graphql_client(
        register_mutation,
        {"input": {"trialId": trial2_id, "siteName": "Shared Site", "country": "UK"}}
    )

    # Should reuse the same site
    assert site2_result["data"]["registerSiteToTrial"]["siteId"] == site_id

    # Verify both trials show the site
    get_trial_query = """
        query GetTrial($id: Int!) {
            trial(id: $id) {
                sites {
                    id
                    name
                }
            }
        }
    """

    trial1_sites = graphql_client(get_trial_query, {"id": trial1_id})
    trial2_sites = graphql_client(get_trial_query, {"id": trial2_id})

    assert len(trial1_sites["data"]["trial"]["sites"]) == 1
    assert len(trial2_sites["data"]["trial"]["sites"]) == 1
    assert trial1_sites["data"]["trial"]["sites"][0]["id"] == site_id
    assert trial2_sites["data"]["trial"]["sites"][0]["id"] == site_id


def test_duplicate_site_registration_fails(graphql_client):
    """Test that registering the same site to a trial twice fails gracefully."""
    # Create trial
    create_trial_mutation = """
        mutation CreateTrial($input: CreateTrialInput!) {
            createTrial(input: $input) {
                id
            }
        }
    """

    trial_result = graphql_client(
        create_trial_mutation,
        {"input": {"name": "Trial for Duplicate Test", "phase": "Phase I"}}
    )
    trial_id = trial_result["data"]["createTrial"]["id"]

    # Register site first time
    register_mutation = """
        mutation RegisterSite($input: RegisterSiteToTrialInput!) {
            registerSiteToTrial(input: $input) {
                siteId
                siteName
            }
        }
    """

    register_input = {
        "input": {
            "trialId": trial_id,
            "siteName": "Duplicate Site",
            "country": "Canada"
        }
    }

    first_result = graphql_client(register_mutation, register_input)
    assert "errors" not in first_result, f"GraphQL errors: {first_result.get('errors')}"

    # Try to register the same site again
    second_result = graphql_client(register_mutation, register_input)

    # Should have error
    assert "errors" in second_result
    error_message = second_result["errors"][0]["message"]
    assert "already linked" in error_message.lower() or "duplicate" in error_message.lower()
