# Deck

Source of truth: `deck-content.md` (39 cards, `---` separated). Generated in Gamma on 2026-09-21 as a 7-page Gamma (the workspace plan caps a generation at 10 cards, so each section is a page), theme **Icebreaker**, 16:9, theme-accent images only.

Gamma (editable, presentable as-is): https://gamma.app/docs/hdqj9qic8yye3vu
Presenter guide (Google Doc): https://docs.google.com/document/d/1RCf4sBcYZMyRUh5jXNd4lkVynZhxBZxq8GP5DPmtWTk/edit

| Page | Gamma | PPTX export (links expire ~28 Sep 2026) |
|---|---|---|
| A — Why | https://gamma.app/docs/hdqj9qic8yye3vu | https://assets.api.gamma.app/export/pptx/hdqj9qic8yye3vu/d255ce8e0b9dae1845b5247c810657dd/A-Why.pptx |
| B — Build | https://gamma.app/docs/e5wf0z2anrvvd3l | https://assets.api.gamma.app/export/pptx/e5wf0z2anrvvd3l/fbf31cbdd2242a4e99d8e3f033388a13/B-Build.pptx |
| C — Extend with LWC | https://gamma.app/docs/qiavk9cqvx8d2s3 | https://assets.api.gamma.app/export/pptx/qiavk9cqvx8d2s3/dd00b571d82efb497a366d81a427c420/C-Extend-with-LWC.pptx |
| D — Package | https://gamma.app/docs/kpitirxraim6jmt | https://assets.api.gamma.app/export/pptx/kpitirxraim6jmt/7e4fe60ed0535bc95cd917ce6bfb99e9/D-Package.pptx |
| E — Deploy | https://gamma.app/docs/4xlojuq7tvp4qx4 | https://assets.api.gamma.app/export/pptx/4xlojuq7tvp4qx4/6c39b0f20ca5e27df19166d3083d7778/E-Deploy.pptx |
| F — Converse | https://gamma.app/docs/iljhcefo53muq0g | https://assets.api.gamma.app/export/pptx/iljhcefo53muq0g/494978d66e49377eea81b216bfbb8558/F-Converse.pptx |
| G — Close & appendix | https://gamma.app/docs/rolibd0gsgd8f39 | https://assets.api.gamma.app/export/pptx/rolibd0gsgd8f39/e2d9f65e874b418cecd58f9297a8df3d/G-Close-and-appendix.pptx |

`merge_parts.py` stitches `parts/part1..7.pptx` into `Tableau-Next-for-Builders.pptx`, which is then uploaded to Google Drive (auto-converts to Google Slides).

Regenerating: edit `deck-content.md`, split at the section dividers, call Gamma `generate_multi_page_gamma` with `textMode: preserve`, `cardSplit: inputTextBreaks`, `themeId: icebreaker`. One full generation costs ~117 Gamma credits.
