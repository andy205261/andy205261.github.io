"""Defang URLs before anything is written to the repo, so no attack link is clickable."""
import re


def defang(s):
    if not isinstance(s, str):
        return s
    s = re.sub(r"(?i)\bhttp(s?)://", r"hxxp\1://", s)
    return s.replace("hotelesms.com", "hotelesms[.]com")
