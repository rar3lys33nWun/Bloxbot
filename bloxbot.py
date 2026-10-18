import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from ddgs import DDGS

VERSION = "2.0.0"
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
UA = "OpportunityScout/2.0 (public-source research)"
SOCIAL = ("linkedin.com", "facebook.com", "instagram.com", "x.com", "twitter.com", "reddit.com", "threads.net", "tiktok.com", "youtube.com", "discord.com")
CATEGORIES = {
 "All opportunities":"business opportunities hiring freelance projects grants funding requests for services",
 "Companies and business leads":"companies businesses vendors partnerships business inquiry",
 "Investors and funding":"startup investors grants funding accelerators applications",
 "Freelance and remote work":"freelance project remote contract client hiring",
 "Jobs and hiring":"we are hiring job openings careers vacancies",
 "Grants and accelerators":"grant application accelerator incubator funding program",
 "Public requests for services":"looking for freelancer need a designer developer request for proposal",
 "Buyers and sellers":"supplier wanted buyer seller wholesale marketplace",
 "Professional networking":"professional collaboration partnership consultant services",
 "Public community discussions":"forum discussion seeking recommendations collaboration project",
 "Cookie / privacy disclosures":"cookie policy privacy notice tracking technologies",
}
st.set_page_config(page_title="BloxBot", page_icon="🔎", layout="wide")
st.title("🤖 BloxBot")
st.caption(f"Public-source opportunity discovery • Version {VERSION}")
st.info("Searches public web results and optionally inspects accessible public webpages. It does not bypass logins, access private groups, collect browser/session cookies, guess personal email addresses, or send messages.")
with st.sidebar:
 st.header("Search settings")
 region=st.text_input("Country / region","Worldwide")
 category=st.selectbox("Opportunity category",list(CATEGORIES))
 source_types=st.multiselect("Source types",["Websites","Public social profiles/posts","Public forums/community pages","Job/freelance boards","Funding/grant pages","Cookie/privacy notices"],default=["Websites","Public social profiles/posts","Public forums/community pages","Job/freelance boards","Funding/grant pages"])
 result_count=st.slider("Results per query",5,30,10)
 inspect=st.checkbox("Inspect accessible public webpages for published contact details",True)
 max_pages=st.slider("Maximum pages to inspect",0,30,12)
st.caption("Use public pages only. Public visibility does not automatically mean permission for bulk marketing.")
topic=st.text_input("What should I find?",placeholder="e.g. businesses seeking web developers, remote jobs, startup grants, suppliers")
def valid_url(u):
 try: return urlparse(u).scheme in ("http","https") and bool(urlparse(u).netloc)
 except: return False
def source_kind(u):
 h=urlparse(u).netloc.lower().removeprefix("www.")
 if any(h==d or h.endswith("."+d) for d in SOCIAL): return "Public social/community page"
 if any(x in h for x in ("upwork","freelancer","wellfound","indeed","remoteok","glassdoor")): return "Job/freelance platform"
 return "Website / public listing"
def search(q,n):
 out=[]
 try:
  with DDGS() as d:
   for x in d.text(q,max_results=n):
    u=x.get("href") or x.get("url") or ""
    if valid_url(u): out.append({"title":x.get("title",""),"url":u.split("#")[0],"snippet":x.get("body","") or x.get("snippet","")})
 except Exception as e: st.warning(f"Search provider issue: {e}")
 return out
def inspect_page(u):
 try:
  r=requests.get(u,timeout=8,headers={"User-Agent":UA},allow_redirects=True)
  if r.status_code!=200 or "text/html" not in r.headers.get("content-type","").lower(): return [],str(r.status_code)
  soup=BeautifulSoup(r.text[:1500000],"html.parser")
  found=set(EMAIL_RE.findall(r.text+" "+soup.get_text(" ",strip=True)))
  clean=[]
  for e in found:
   e=e.strip(".,;:()[]{}<>").lower()
   if e.startswith(("noreply@","no-reply@","donotreply@","do-not-reply@")): continue
   if e.endswith(("@example.com","@example.org","@test.com","@invalid.com")): continue
   clean.append(e)
  return sorted(set(clean)),str(r.status_code)
 except Exception: return [],"not fetched"
if "results" not in st.session_state: st.session_state.results=pd.DataFrame()
if st.button("🔍 Search public sources",type="primary"):
 if not topic.strip(): st.error("Enter a search topic.")
 elif not source_types: st.error("Select at least one source type.")
 else:
  hints=[]
  if "Websites" in source_types: hints.append("")
  if "Public social profiles/posts" in source_types: hints += [" site:linkedin.com/posts"," site:facebook.com"," site:instagram.com"," site:x.com"]
  if "Public forums/community pages" in source_types: hints += [" site:reddit.com"," forum"," community"]
  if "Job/freelance boards" in source_types: hints += [" site:upwork.com"," site:freelancer.com"," site:wellfound.com"," site:indeed.com"]
  if "Funding/grant pages" in source_types: hints += [" grant"," funding"," accelerator"]
  if "Cookie/privacy notices" in source_types: hints += [" cookie policy"," privacy notice"]
  queries=list(dict.fromkeys(f"{topic} {CATEGORIES[category]} {region} {h}".strip() for h in hints))[:10]
  raw=[]
  bar=st.progress(0)
  for i,q in enumerate(queries):
   raw.extend(search(q,result_count)); bar.progress((i+1)/len(queries)); time.sleep(.2)
  unique={x["url"]:x for x in raw}
  rows=[]; inspected=0
  for x in unique.values():
   emails=[]; status=""
   if inspect and inspected<max_pages and source_kind(x["url"])=="Website / public listing":
    emails,status=inspect_page(x["url"]); inspected+=1
   rows.append({"discovered_at_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),"category":category,"region_filter":region,"title":x["title"],"snippet":x["snippet"],"source_type":source_kind(x["url"]),"source_url":x["url"],"published_professional_emails":"; ".join(emails),"page_fetch_status":status,"contact_review_status":"Needs human review" if emails else "No public email found","outreach_status":"Not contacted","notes":""})
  st.session_state.results=pd.DataFrame(rows)
df=st.session_state.results
if not df.empty:
 st.subheader(f"Results ({len(df)})")
 a,b,c=st.columns(3); a.metric("Public results",len(df)); b.metric("Results with published emails",int((df["published_professional_emails"].fillna("")!="").sum())); c.metric("Unique domains",df["source_url"].map(lambda u:urlparse(u).netloc.lower()).nunique())
 edited=st.data_editor(df,use_container_width=True,hide_index=True,num_rows="dynamic")
 st.session_state.results=edited
 st.download_button("Download CSV",edited.to_csv(index=False).encode("utf-8-sig"),"bloxbot_results.csv","text/csv")
 try:
  import io
  buf=io.BytesIO()
  with pd.ExcelWriter(buf,engine="openpyxl") as writer: edited.to_excel(writer,index=False,sheet_name="Opportunities")
  st.download_button("Download Excel",buf.getvalue(),"bloxbot_results.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
 except Exception: pass
st.divider()
st.subheader("Responsible contact use")
st.markdown("- Results are leads to review, not proof of marketing consent.\\n- Use addresses published for professional contact or collected with appropriate permission.\\n- Do not infer private Gmail/Outlook addresses.\\n- Respect platform terms, privacy requirements, access controls, and community rules.\\n- Keep opt-outs and hard bounces suppressed if you later add outreach.\\n- A valid-looking address does not prove an inbox is active; replies are stronger engagement evidence than opens.")
st.caption("Prototype only: no email sending, private-group access, browser-cookie collection, persistent database, or scheduled background searches.")
