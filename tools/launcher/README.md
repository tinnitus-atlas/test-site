# Launcher (first piece: setup wizard)

The launcher will stand up a new cited knowledge-graph project with only the owner's approvals. Its first piece, the
**setup wizard**, gives a repository the Ship it merge app in about four clicks instead of ten manual steps:

1. **Connect GitHub**: opens GitHub's page for a one-day setup key with the permissions filled in; paste it back.
2. **Create the app**: opens GitHub's "Create GitHub App" page with everything filled in; click Create.
3. **Install**: pick the repository; click Install.
4. **Finish**: the wizard creates the protected `ship-it` environment (main only), stores the app ID and the app's
   private key (encrypted; never written to disk or shown), adds the app to the merge rule's bypass list, and checks
   the app can act on the repository.

Run from a clone: `python3 -m tools.launcher.setup_wizard.server --repo OWNER/REPO` and open the address it prints.
It listens on this computer only. The encryption step needs the PyNaCl library (the packaged app will include it).

Status: built and tested against a stand-in GitHub; not yet run against GitHub itself. Creating a new organisation
stays a manual step: GitHub offers no way to do it from code on github.com.
