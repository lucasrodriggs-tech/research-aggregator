# Marks proxy Worker

Deploy steps (one-time, must be done by the repo owner -- needs your own
Cloudflare account and a scoped GitHub token):

1. Create a free Cloudflare account at https://dash.cloudflare.com/sign-up if you don't have one.
2. Install Wrangler (Cloudflare's CLI) if not already present:

       npm install -g wrangler

3. From the `worker/` directory, log in (opens a browser):

       wrangler login

4. Create a GitHub Personal Access Token scoped to ONLY this repo, with
   `Contents: Read and write` permission (fine-grained token,
   https://github.com/settings/personal-access-tokens/new -> Repository
   access -> Only select repositories -> research-aggregator -> Permissions
   -> Contents -> Read and write). Copy the token.

5. Set it as a Worker secret (paste the token when prompted -- this stores
   it securely in Cloudflare, never in this repo):

       wrangler secret put GITHUB_TOKEN

6. Deploy:

       wrangler deploy

   This prints the live Worker URL, something like
   `https://research-aggregator-marks.<your-subdomain>.workers.dev`.
   That URL is needed to finish the site integration (see the main repo's
   implementation plan, Task 7).

## Security note

The CORS headers in this Worker restrict browser-based callers only—they are
not authentication. Once deployed, the Worker URL is publicly reachable and
can be called by anyone with the URL via direct requests (curl, scripts, etc.),
since CORS enforcement is a browser feature, not a server feature. The practical
impact is limited (worst case, someone pollutes data/marks.json with arbitrary
mark entries, affecting future re-ranking but not exposing sensitive data or
incurring costs), but it's worth understanding before deployment.
