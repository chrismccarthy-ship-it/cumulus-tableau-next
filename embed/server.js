/**
 * Cumulus Embedding SDK sample — Express server.
 *
 * Implements the auth path from "Set Up Salesforce for Embedding Tableau Next Externally":
 *   1. GET /oauth2/auth      → redirect to Salesforce authorize (External Client App, web-server flow, PKCE)
 *   2. GET /getAccessToken   → exchange the code for an access token (+ instance_url)
 *   3. POST /services/oauth2/singleaccess → frontdoor URL, handed to the browser as `authCredential`
 *
 * Nothing secret reaches the browser except the short-lived frontdoor URL, and only when the
 * page asks for it (GET /frontdoor) after login.
 */
import express from "express";
import session from "express-session";
import crypto from "crypto";
import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";

dotenv.config();
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();

const LOGIN_URL = process.env.SF_LOGIN_URL || "https://login.salesforce.com"; // or your My Domain login URL
const CLIENT_ID = process.env.SF_CLIENT_ID; // ECA consumer key
const CLIENT_SECRET = process.env.SF_CLIENT_SECRET; // only if "Require Secret for Web Server Flow" is on
const ORG_URL = process.env.SF_ORG_URL; // Lightning URL, e.g. https://xxx.lightning.force.com
const PORT = Number(process.env.PORT || 3000);
const REDIRECT_URI = process.env.SF_REDIRECT_URI || `http://localhost:${PORT}/getAccessToken`;

app.use(session({ secret: process.env.SESSION_SECRET || crypto.randomBytes(16).toString("hex"), resave: false, saveUninitialized: true }));
app.use(express.static(path.join(__dirname, "public")));
app.use("/sdk", express.static(path.join(__dirname, "node_modules", "@salesforce", "analytics-embedding-sdk", "dist")));

function pkce() {
  const codeVerifier = crypto.randomBytes(96).toString("base64url");
  const codeChallenge = crypto.createHash("sha256").update(codeVerifier).digest().toString("base64url");
  return { codeVerifier, codeChallenge };
}

app.get("/oauth2/auth", (req, res) => {
  const { codeVerifier, codeChallenge } = pkce();
  req.session.codeVerifier = codeVerifier;
  const params = new URLSearchParams({ response_type: "code", client_id: CLIENT_ID, redirect_uri: REDIRECT_URI,
    scope: "api refresh_token web", code_challenge: codeChallenge, code_challenge_method: "S256" });
  res.redirect(`${LOGIN_URL}/services/oauth2/authorize?${params}`);
});

app.get("/getAccessToken", async (req, res) => {
  const { code } = req.query;
  if (!code) return res.status(400).send("Missing authorization code");
  const params = new URLSearchParams({ grant_type: "authorization_code", client_id: CLIENT_ID, redirect_uri: REDIRECT_URI, code: String(code) });
  if (req.session.codeVerifier) params.append("code_verifier", req.session.codeVerifier);
  if (CLIENT_SECRET) params.append("client_secret", CLIENT_SECRET);
  const r = await fetch(`${LOGIN_URL}/services/oauth2/token`, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: params });
  if (!r.ok) return res.status(500).send(`Token exchange failed: ${await r.text()}`);
  const { access_token, instance_url } = await r.json();
  req.session.accessToken = access_token;
  req.session.instanceUrl = instance_url;
  res.redirect("/");
});

/** Frontdoor URLs are short-lived: the page calls this right before initializing the SDK. */
app.get("/frontdoor", async (req, res) => {
  if (!req.session.accessToken) return res.status(401).json({ error: "not logged in" });
  const r = await fetch(`${req.session.instanceUrl}/services/oauth2/singleaccess`, {
    method: "POST", headers: { accept: "application/json", authorization: `Bearer ${req.session.accessToken}`, "content-type": "application/x-www-form-urlencoded" }, body: "" });
  if (!r.ok) return res.status(500).json({ error: `singleaccess responded ${r.status}` });
  const { frontdoor_uri } = await r.json();
  res.json({ authCredential: frontdoor_uri, orgUrl: ORG_URL });
});

app.get("/logout", (req, res) => { req.session.destroy(() => res.redirect("/")); });

app.listen(PORT, () => console.log(`Cumulus embed sample on http://localhost:${PORT}  (ECA callback must be ${REDIRECT_URI})`));
