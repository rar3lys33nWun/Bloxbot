# BloxBot 3.1

A Streamlit public-source opportunity discovery prototype designed to search for **individuals and companies**: freelancers, independent professionals, potential clients, creators/collaborators, businesses, jobs, grants, suppliers, and public opportunities.

## Deploy on Streamlit Community Cloud

Put these files in the root of your GitHub repository:
- `bloxbot.py`
- `requirements.txt`
- `README.md`

Choose `bloxbot.py` as the app's main file.

## Notes

- Maximum search depth runs multiple different query angles; results depend on the search provider, region, and source availability. It cannot guarantee 500 results in every search.
- Entity type and relevance scores are heuristic hints and should be reviewed.
- A published email is not proof that an inbox is active or that its owner has consented to marketing. Only contact people where there is an appropriate legal basis and comply with opt-out requirements.
- Public social/profile pages are not guaranteed to be fetchable. The app does not bypass logins or access controls.
- The suppression list and results are session-only; use persistent storage and authenticated webhooks before production use.
- The Resend mailer is a prototype and should not be used for unsolicited bulk email.
