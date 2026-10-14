---
type: llm
---

PASS if the reply recommends the Launcher User role, lists only roles that exist in Domino (Owner, Contributor, Results Consumer, Launcher User, Project Importer), and answers the visibility question with the Searchable setting (as opposed to Private). Saying Public visibility is unavailable on Domino Cloud, or omitting Public, is fine.
FAIL if it invents roles such as Admin, Editor, Viewer or Reader as project collaborator roles, or offers an "Organization" visibility setting.
