import io, re, time
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from ddgs import DDGS

VERSION = "3.1.0"
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
UA = "BloxBot/3.0 (+public opportunity research)"
st.set_page_config(page_title="BloxBot", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.block-container{padding-top:1.4rem;max-width:1400px}
.hero{padding:1.4rem 1.5rem;border-radius:18px;background:linear-gradient(120deg,#18233d,#203d4b);color:white;margin-bottom:1rem}
.hero h1{font-size:2.25rem;margin:0}.hero p{opacity:.88;margin:.4rem 0 0}
div[data-testid="stMetric"]{border:1px solid #30394a;border-radius:14px;padding:12px}
.stButton button{border-radius:10px;min-height:2.8rem}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🤖 BloxBot</h1><p>Find opportunities. Discover public business contacts. Track outreach responsibly.</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.subheader("Search controls")
    region = st.text_input("Target country / region", "Worldwide")
    category = st.selectbox("Opportunity type", [
        "All categories (people + companies)", "Individuals / freelancers", "Potential clients",
        "Creators / collaborators", "Companies / business leads", "Jobs / hiring",
        "Freelance projects", "Grants / accelerators", "Investors / funding",
        "Suppliers / buyers", "Professional services", "Public community opportunities"
    ])
    search_depth = st.select_slider("Search depth", options=["Quick", "Balanced", "Deep", "Maximum"], value="Maximum")
    include_social = st.checkbox("Public social/profile pages", True)
    include_community = st.checkbox("Public forums and community posts", True)
    inspect_contacts = st.checkbox("Find contact/about pages and published emails", True)
    st.caption("Only public pages accessible without bypassing logins or access controls.")

TERMS = {
"All categories (people + companies)":"freelancer OR independent consultant OR creator OR hiring OR seeking services OR company OR startup OR collaboration",
"Individuals / freelancers":"freelancer OR independent consultant OR self-employed OR portfolio OR available for freelance work",
"Potential clients":"looking for a freelancer OR seeking a developer OR need a designer OR seeking consultant OR request for proposal",
"Creators / collaborators":"creator partnership OR influencer collaboration OR brand partnership OR looking for collaborators",
"Companies / business leads":"company OR business OR agency OR startup OR vendor OR partnership contact",
"Jobs / hiring":"hiring OR careers OR job opening OR recruitment OR contractor wanted",
"Freelance projects":"freelance project OR contract OR remote client OR looking for freelancer",
"Grants / accelerators":"grant OR accelerator OR incubator OR funding program",
"Investors / funding":"investor OR venture capital OR startup funding OR angel investor",
"Suppliers / buyers":"supplier wanted OR wholesale buyer OR procurement OR vendor",
"Professional services":"consultant OR designer OR developer OR professional services",
"Public community opportunities":"seeking recommendations OR collaboration OR looking for services forum"
}
N = {"Quick":8, "Balanced":16, "Deep":28, "Maximum":40}[search_depth]
if "leads" not in st.session_state: st.session_state.leads = pd.DataFrame()
if "suppression" not in st.session_state: st.session_state.suppression = set()

def valid_http(u):
    try: return urlparse(u).scheme in ("http","https") and bool(urlparse(u).netloc)
    except Exception: return False

def web_search(q, limit):
    found=[]
    try:
        with DDGS() as ddgs:
            for x in ddgs.text(q, max_results=limit):
                u=x.get("href") or x.get("url") or ""
                if valid_http(u):
                    found.append({"title":x.get("title",""),"url":u.split("#")[0],"snippet":x.get("body","") or x.get("snippet","")})
    except Exception as e:
        st.warning(f"One search failed: {e}")
    return found

def host_type(url):
    host=urlparse(url).netloc.lower().replace("www.","")
    social=("linkedin.com","facebook.com","instagram.com","x.com","twitter.com","reddit.com","threads.net","tiktok.com","youtube.com")
    if any(host==d or host.endswith("."+d) for d in social): return "Social / community"
    if any(x in host for x in ("indeed.","upwork.","freelancer.","wellfound.","remoteok.","glassdoor.")): return "Job / freelance platform"
    return "Website / listing"

def fetch_html(url):
    try:
        r=requests.get(url,headers={"User-Agent":UA},timeout=8,allow_redirects=True)
        if r.status_code==200 and "text/html" in r.headers.get("content-type","").lower():
            return r.text[:1200000],str(r.status_code)
        return "",str(r.status_code)
    except Exception: return "","fetch failed"

def extract_emails(html):
    soup=BeautifulSoup(html,"html.parser")
    candidates=set(EMAIL_RE.findall(html+" "+soup.get_text(" ",strip=True)))
    result=[]
    for e in candidates:
        e=e.strip(".,;:()[]{}<>").lower()
        if e.startswith(("no-reply@","noreply@","donotreply@","do-not-reply@")): continue
        if e.endswith(("@example.com","@example.org","@test.com","@invalid.com")): continue
        result.append(e)
    return sorted(set(result))

def discover_contact_pages(url, html):
    soup=BeautifulSoup(html,"html.parser")
    candidates=[]
    for a in soup.find_all("a",href=True):
        label=(a.get_text(" ",strip=True)+" "+a["href"]).lower()
        if any(word in label for word in ("contact","about","team","staff","support","company")):
            dest=urljoin(url,a["href"])
            if valid_http(dest) and urlparse(dest).netloc==urlparse(url).netloc and dest not in candidates:
                candidates.append(dest)
    return candidates[:3]

topic=st.text_input("Search for",placeholder="e.g. marketing agencies hiring contractors, small companies, grant opportunities")
left,right=st.columns([1,3])
with left:
    run=st.button("🔎 Find opportunities",type="primary",use_container_width=True)
with right:
    st.caption("Use a role, industry, service, company type, or location to improve relevance.")

if run:
    if not topic.strip():
        st.error("Enter a search phrase first.")
    else:
        base = TERMS[category]
        # Search several distinct intents instead of repeating company-only queries.
        queries = [
            f'"{topic}" {base} {region}',
            f'{topic} individual freelancer consultant portfolio {region}',
            f'{topic} "looking for" OR "seeking" OR "need a" freelancer {region}',
            f'{topic} independent professional creator collaboration contact {region}',
            f'{topic} public email contact professional {region}',
            f'{topic} job contract project opportunity {region}',
            f'{topic} startup small business agency partnership {region}',
            f'{topic} recent public post request recommendation service {region}',
        ]
        if include_social:
            queries.extend([
                f'{topic} freelancer consultant professional site:linkedin.com {region}',
                f'{topic} creator collaboration contact site:instagram.com OR site:youtube.com {region}',
                f'{topic} public professional profile site:facebook.com OR site:x.com {region}',
            ])
        if include_community:
            queries.extend([
                f'{topic} looking for freelancer OR consultant site:reddit.com {region}',
                f'{topic} seeking services OR collaboration forum community {region}',
            ])
        if category == "All categories (people + companies)":
            queries.extend([
                f'{topic} "freelancer" OR "independent consultant" OR "available for projects" {region}',
                f'{topic} "looking for a developer" OR "need a designer" OR "seeking an agency" {region}',
                f'{topic} "contact" "about me" OR portfolio {region}',
            ])
        rows={}
        prog=st.progress(0)
        for i,q in enumerate(queries):
            for item in web_search(q,N):
                rows.setdefault(item["url"],item)
            prog.progress((i+1)/len(queries))
            time.sleep(.15)
        prog.empty()
        allitems=list(rows.values())
        records=[]
        bar=st.progress(0)
        for i,item in enumerate(allitems):
            emails=[]; pages_checked=[]; status="not inspected"
            if inspect_contacts and host_type(item["url"])=="Website / listing":
                html,status=fetch_html(item["url"])
                if html:
                    emails.extend(extract_emails(html))
                    contact_pages=discover_contact_pages(item["url"],html)
                    for cp in contact_pages:
                        subhtml,_=fetch_html(cp)
                        pages_checked.append(cp)
                        if subhtml: emails.extend(extract_emails(subhtml))
            combined = (item["title"] + " " + item["snippet"] + " " + item["url"]).lower()
            individual_terms = ("freelancer", "consultant", "portfolio", "creator", "independent", "personal website", "available for work", "looking for a", "need a developer", "seeking a")
            company_terms = ("company", "inc.", "llc", "ltd", "agency", "corporation", "startup", "careers", "enterprise")
            person_score = sum(term in combined for term in individual_terms)
            company_score = sum(term in combined for term in company_terms)
            entity_kind = "Individual / professional" if person_score > company_score else ("Company / organization" if company_score > person_score else "Unclear — review")
            relevance_score = min(100, 35 + 8 * sum(word.lower() in combined for word in re.findall(r"[A-Za-z0-9]+", topic) if len(word) > 2) + 5 * min(person_score + company_score, 4))
            records.append({
                "discovered_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "category":category,"entity_type":entity_kind,"relevance_score_estimate":relevance_score,
                "region":region,"title":item["title"],"summary":item["snippet"],
                "source_type":host_type(item["url"]),"source_url":item["url"],
                "public_emails":", ".join(sorted(set(emails))),
                "contact_pages_checked":"; ".join(pages_checked),"fetch_status":status,
                "inbox_status":"Unknown — not verified","permission_basis":"Review required",
                "outreach_status":"Not contacted","notes":""
            })
            bar.progress((i+1)/max(1,len(allitems)))
        bar.empty()
        st.session_state.leads=pd.DataFrame(records)

df=st.session_state.leads
if not df.empty:
    st.subheader("Your discovery results")
    filter1, filter2 = st.columns(2)
    with filter1:
        entity_filter = st.selectbox("Filter by result type", ["All", "Individual / professional", "Company / organization", "Unclear — review"])
    with filter2:
        min_relevance = st.slider("Minimum estimated relevance", 0, 100, 0)
    view_df = df.copy()
    if entity_filter != "All": view_df = view_df[view_df["entity_type"] == entity_filter]
    view_df = view_df[view_df["relevance_score_estimate"] >= min_relevance]
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Filtered results",len(view_df))
    m2.metric("Individual results",int((df["entity_type"]=="Individual / professional").sum()))
    m3.metric("Company results",int((df["entity_type"]=="Company / organization").sum()))
    m4.metric("With public email",int((df["public_emails"].fillna("")!="").sum()))
    st.warning("BloxBot cannot truthfully label 100 inboxes active based on a search. A published address or successful delivery does not prove that a person reads it. Use an authorized verification provider or real delivery events, and suppress bounces/opt-outs.")
    edited=st.data_editor(view_df,use_container_width=True,hide_index=True,num_rows="dynamic",column_config={
        "source_url":st.column_config.LinkColumn("Source URL"),
        "public_emails":st.column_config.TextColumn("Publicly published emails"),
        "permission_basis":st.column_config.SelectboxColumn("Contact basis",options=["Review required","Public professional contact","Explicit opt-in","Existing relationship","Do not contact"]),
        "outreach_status":st.column_config.SelectboxColumn("Outreach status",options=["Not contacted","Queued","Sent","Delivered","Replied","Hard bounce","Unsubscribed","Do not contact"])
    })
    # Preserve the full result set when a display filter is active.
    if entity_filter == "All" and min_relevance == 0:
        st.session_state.leads=edited
    st.download_button("⬇️ Export filtered CSV",edited.to_csv(index=False).encode("utf-8-sig"),"bloxbot_leads.csv","text/csv")
    buf=io.BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as writer: edited.to_excel(writer,index=False,sheet_name="Leads")
    st.download_button("⬇️ Export Excel",buf.getvalue(),"bloxbot_leads.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.divider()
tabs=st.tabs(["✉️ Mailer","📊 Engagement","🛡️ Suppression & safety"])
with tabs[0]:
    st.subheader("Send to reviewed contacts")
    st.write("Mailer uses Resend. Only send to contacts you are authorized to email; do not use a raw scraped list for unsolicited bulk outreach.")
    api_key=st.text_input("Resend API key",type="password",help="Stored only for this Streamlit session. For production, use Streamlit Secrets.")
    sender=st.text_input("Verified sender address",placeholder="you@your-verified-domain.com")
    subject=st.text_input("Email subject")
    body=st.text_area("Message",height=180,placeholder="Write a relevant, honest message and include your identity and an opt-out method.")
    if not df.empty:
        available=df.copy()
        available["email_for_send"]=available["public_emails"].fillna("").str.split(",").str[0].str.strip()
        available=available[(available["email_for_send"]!="") & (available["permission_basis"].isin(["Explicit opt-in","Existing relationship","Public professional contact"]))]
        st.caption(f"{len(available)} rows have a selected contact basis. Review every recipient before sending.")
        recipients=st.text_area("Recipient addresses (one per line; reviewed/authorized only)",value="",placeholder="Paste approved recipient addresses, one per line")
        confirm=st.checkbox("I confirm these recipients are appropriate to contact and my message complies with applicable rules.")
        if st.button("Send test / approved email"):
            if not api_key or not sender or not subject or not body or not recipients.strip():
                st.error("Complete all fields.")
            elif not confirm:
                st.error("Confirm authorized recipients before sending.")
            else:
                emails=list(dict.fromkeys(x.strip() for x in recipients.splitlines() if "@" in x))
                blocked = [e for e in emails if e.lower() in st.session_state.suppression]
                if blocked:
                    st.error("Suppressed address(es) cannot be sent: " + ", ".join(blocked))
                elif len(emails)>10:
                    st.error("This UI limits each send action to 10 recipients. Send a small reviewed batch and monitor results.")
                else:
                    payload={"from":sender,"to":emails,"subject":subject,"text":body}
                    try:
                        resp=requests.post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},json=payload,timeout=20)
                        if resp.ok: st.success(f"Request accepted by Resend: {resp.text}")
                        else: st.error(f"Resend rejected the request ({resp.status_code}): {resp.text}")
                    except Exception as e: st.error(f"Send failed: {e}")
    else:
        st.caption("Run a search first. Sending remains disabled until you provide reviewed recipients and sender details.")
with tabs[1]:
    st.subheader("Engagement tracking")
    st.markdown("Track outcomes in the editable results table: **Sent → Delivered → Replied**, or mark **Hard bounce / Unsubscribed / Do not contact**. Opens are not reliable proof of human engagement. For automated event tracking, configure Resend webhooks and a persistent database.")
    st.write("Resend supports delivery, bounce, complaint, open and click events through webhooks: https://resend.com/features/webhooks")
with tabs[2]:
    st.subheader("Suppression list")
    suppress_input=st.text_area("Addresses to suppress (one per line)")
    if st.button("Add to this session's suppression list"):
        st.session_state.suppression.update(x.strip().lower() for x in suppress_input.splitlines() if "@" in x)
        st.success(f"{len(st.session_state.suppression)} address(es) suppressed for this session.")
    st.write(f"Suppressed in this session: {len(st.session_state.suppression)}")
    st.caption("This prototype's suppression list is session-only; use persistent storage before production use.")

st.caption("BloxBot 3.1 • Expanded individual + company discovery. Search quality varies by provider and region; relevance scores are heuristic estimates, not guarantees. Public pages only; no private-group or access-control bypass.")
