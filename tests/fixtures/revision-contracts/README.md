# Persisted revision contracts

These three JSON files were produced by the pre-extraction `revisions.py` at
`a3cbeeb2b9a30bf40a8bd62eada9df17263be827`, using
`tests/revision_contract_fixture.py` and a fixed UTC clock. They cover a version-1
revision, a legacy version-1 edition and a named-view version-2 edition. The
fixture retains Unicode, floats, CRLF control bytes, dependency ordering and
project-relative identities. Tests compare newly captured records byte for byte,
and independently check the stored seals and per-kind version acceptance.

Movie inputs are explicitly synthetic text placeholders. These fixtures test
serialized contracts, not media decoding or artistic approval. Native edition
and recovery tests establish the separate media path.

Do not regenerate the expected bytes merely to make a refactor pass. A deliberate
contract change needs separate compatibility treatment.
