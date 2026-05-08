# Runtime troubleshooting

## Optional torch / Kronos runtime

The `model prediction / AI prediction / trend prediction` command path depends on the bundled `Kronos` model code, which in turn requires a separate `torch` runtime.

On lightweight VPS deployments this optional stack is easy to break in two ways:

- `pip install torch ...` can hang or time out during download
- partial hotfixes can leave `stock_ai` in a broken import state even when the main plugin should still work

Current fork policy:

- regular stock/news/watchlist/market features stay enabled
- Kronos-based prediction commands are disabled by default
- do not block plugin startup on `torch` / `Kronos`

## Dashboard request path

The `market overview` image depends on these Eastmoney endpoints:

- `clist/get`: main indexes, industry leaders, concept leaders
- `updowndistribution`: market breadth histogram
- `stock/get`: extra blocks for gold `118.AU9999` and treasury futures `220.TLM`

The first two categories are required. The gold and treasury blocks are optional extras.

## 2026-04-10 incident

Symptoms:

- user sends the market overview command
- bot replies with `[SayuStock] request error, code: -400016`
- GSUID log repeats `push2.eastmoney.com/api/qt/stock/get failed, trying DC-Token`

Root causes:

1. `draw_info_img()` treated every concurrent subrequest as mandatory.
2. A failure on gold or treasury `stock/get` aborted the whole image.
3. `get_dc_token()` used `wait_until="networkidle"`, which is fragile on pages with long-lived connections.
4. After refreshing cookies, `stock_request()` did not explicitly resend the updated headers on retry.

## Fixes in this patch

### 1. Graceful degradation for market overview

Required data remains strict:

- main indexes
- industry up/down lists
- concept up/down lists
- breadth histogram

Optional data now degrades cleanly:

- gold `118.AU9999`
- treasury futures `220.TLM`

If these two extras fail, the image still renders.

## 2026-04-12 deployment regression note

The Huawei VPS later showed a separate deployment-side regression:

1. the live plugin working tree contained unresolved Git conflict markers in `SayuStock/utils/stock/request.py`
2. the local repo still had the old `draw_info.py` logic that treated AU/TLM as hard requirements

Recovery / prevention:

- reset the VPS plugin repo back to a clean committed state before restart
- keep `draw_info.py` in the Git repo aligned with the graceful-degradation behavior above
- after each deploy, run both:
  - all-weather
  - market overview

### 2. Stabilized DC-Token refresh flow

- trigger token refresh on HTTP 403
- resend updated headers on retry
- switch Playwright navigation to `domcontentloaded`
- wait briefly for cookies to be written
- auto-run `playwright install chromium` if the browser runtime is missing

## VPS regression checklist

After deploy, retest:

1. market overview
2. watchlist / my stocks
3. single stock quote
4. all-weather / futures overview

If `-400016` appears again, inspect:

- `gsuid_core/data/logs/YYYY-MM-DD.log`
- whether the failing URL is `push2.eastmoney.com/api/qt/stock/get`
- whether `Failed to fetch DC-Token` appears
- whether Playwright Chromium exists on the server

## 2026-04-10 all-weather follow-up

Symptoms:

- the `all-weather` image renders the top `international market` block
- middle and bottom blocks are blank
- GSUID logs repeat `stock/get failed, trying DC-Token`
- crypto requests log network errors

Confirmed split:

- `international market` uses `clist/get` and can still succeed
- commodity / bond / FX blocks depend on `stock/get`
- crypto depends on OKX

Confirmed root causes:

1. `stock/get` on the Huawei VPS succeeds with a clean request, but fails when stale built-in Eastmoney cookies are injected.
2. The plugin still carried cookie defaults in:
   - `SayuStock/utils/constant.py`
   - `SayuStock/stock_config/config_default.py`
   - `SayuStock/utils/stock/request.py`
3. The Huawei VPS cannot reach OKX directly, but can reach it through the local Clash proxy `http://127.0.0.1:7890`.

Fixes in this patch:

- remove built-in Eastmoney cookie defaults
- start Eastmoney requests with a clean header and no session cookies
- only inject a freshly fetched DC token on retry
- add OKX proxy fallback for the all-weather crypto panel
- use `httpx.AsyncHTTPTransport` for OKX proxy mounts in async clients

## 2026-04-15 all-weather slowdown follow-up

Symptoms:

- `all-weather` eventually succeeds, but becomes much slower than before
- GSUID logs show repeated warnings like:
  - `push2.eastmoney.com/api/qt/stock/trends2/get failed, trying DC-Token`

Root cause:

1. `draw_future_img()` fans out many Eastmoney `stock/*` requests concurrently.
2. `stock_request()` was not reusing an already-fetched DC token on the first attempt.
3. once one request hit HTTP 403, multiple concurrent requests could each trigger their own `get_dc_token()` flow.
4. on VPS this meant repeated Playwright cookie bootstraps, extra warnings, and a much slower all-weather render.

Fix in this patch:

- reuse cached DC token before the first request for `https://push2.eastmoney.com/api/qt/stock/*`
- serialize token refresh with an async lock
- only force-refresh the token after an actual 403 retry path

Expected effect:

- the first Eastmoney stock request may still need one token bootstrap after process start
- subsequent all-weather requests should avoid the repeated warning burst
- total render time should drop materially because concurrent requests no longer all launch their own token refresh path

## 2026-04-15 push2his follow-up

Symptoms:

- ll-weather is still much slower than expected even after the first DC-token cache patch
- logs still show repeated warnings like:
  - push2his.eastmoney.com/api/qt/stock/trends2/get failed, trying DC-Token
- US ETF / bond / FX panels spend several extra seconds per symbol

Root cause:

1. the previous patch only treated https://push2.eastmoney.com/api/qt/stock/* as requiring a cached DC token on the first attempt
2. 	rends2/get and other historical stock endpoints actually live under https://push2his.eastmoney.com/api/qt/stock/*
3. those requests therefore still sent a token-less first request, failed once, then forced a token refresh / retry
4. on the VPS this added ~3-4 seconds per push2his request and kept the warning spam alive

Fix in this patch:

- extend the first-attempt cached-token path to both:
  - https://push2.eastmoney.com/api/qt/stock/*
  - https://push2his.eastmoney.com/api/qt/stock/*

Expected effect:

- 	rends2/get should stop doing a guaranteed fail-first cycle
- all-weather commodity / bond / FX sections should speed up materially
- warning volume in GSUID logs should drop again because cached DC cookies are now reused for both live and historical Eastmoney stock APIs

## 2026-05-06 DC-token global declaration compile guard

Symptom:

- `python -m py_compile SayuStock/utils/stock/request.py` failed with:
  - `SyntaxError: name 'LAST_DC_REFRESH' is used prior to global declaration`

Root cause:

1. `get_dc_token()` read `LAST_DC_REFRESH` before its inner `global LAST_DC_REFRESH` declaration.
2. Python applies `global` to the whole function body, so late declarations after a prior textual use are invalid.

Fix in this patch:

- move `LAST_DC_REFRESH` and `LAST_DC_FAILURE` into the top-level `global` declaration at the start of `get_dc_token()`
- remove the inner `global` statements

Verification:

- `python -m py_compile SayuStock/utils/stock/request.py`

## 2026-05-06 all-weather acceleration: no active polling

Decision:

- do **not** add minute-level scheduled preloading for Eastmoney endpoints
- acceleration must not create background request pressure that can trip Eastmoney risk controls

Fixes in this patch:

- persist the Eastmoney DC cookie header to `dc_token.json` under the SayuStock resource root
- load the persisted DC token before starting Playwright, and only launch Playwright when no valid persisted token exists or an actual 403 forces refresh
- let the first real 403 replace a bad persisted token, but coalesce concurrent 403 refreshes so only one coroutine starts Playwright in a burst
- coalesce concurrent `async_file_cache` misses per cache file so simultaneous commands do not stampede the same Eastmoney endpoint
- add a 20-second in-process `draw_future_img()` result cache/lock for repeated group spam; this is not a scheduler and sends no background Eastmoney requests

Validation:

- `python -m py_compile SayuStock/utils/stock/request.py SayuStock/utils/stock/utils.py SayuStock/stock_info/draw_future.py`
- local draw simulation with stubbed gsuid runtime returned image size `900x1395`; first render `1.0189s`, second in-process cache hit `0.000008s`


Follow-up from VPS validation:

- real VPS draw validation showed that unbounded `force_refresh=True` could still cause a Playwright refresh burst when many concurrent symbol requests all received 403
- `get_dc_token(force_refresh=True, current_token=...)` now detects when another coroutine has already replaced the token, and also applies a short force-refresh cooldown after a browser refresh
- this keeps the no-polling design while avoiding a 403-triggered token refresh stampede
- VPS synthetic concurrency validation: 12 concurrent `force_refresh=True` calls with the same stale token performed exactly 1 fake browser fetch, then reused the refreshed token during the cooldown
- VPS service validation: `systemctl restart gsuid` completed, `systemctl is-active gsuid` returned `active`, and SayuStock loaded successfully in `journalctl`

Operational note:

- normal VPS `git fetch` from GitHub timed out from the server network; production was hot-deployed by SFTP after local commit/push, then `systemctl restart gsuid` and journal checks were run

## 2026-05-06 all-weather commodity/bond/FX sections hidden

Symptom:

- the `all-weather` image rendered `GLOBAL INDICES` and `CRYPTO`, but skipped `COMMODITIES`, `BONDS & YIELDS`, and `FOREX`

Root cause:

1. the dynamic all-weather renderer only draws a section when fetched item names exactly match the configured section labels
2. Eastmoney single-symbol responses can return display names that differ from the local labels used in `commodity`, `bond`, and `whsc`
3. on the VPS, the single-symbol `push2/push2his ... /stock/*` path can disconnect repeatedly while the `clist/get` list path still works
4. one failing sub-request could also raise through `asyncio.gather()` and collapse the whole section to `None`

Fix in this patch:

- fetch all-weather commodity, bond, and FX snapshots through the faster `clist/get` list endpoint with explicit `i:<secid>` symbols
- normalize all-weather single-symbol items to the configured display label before rendering
- let the renderer prefer dictionary-key matches for section data
- gather per-symbol sub-requests with `return_exceptions=True` so one bad symbol does not hide the whole section

Validation:

- `python -m py_compile SayuStock/stock_info/draw_future.py SayuStock/utils/stock/request.py SayuStock/utils/stock/utils.py`
- local `draw_future_img()` list-endpoint simulation rendered commodity, bond, FX, and crypto blocks; image size `900x1170`, elapsed `0.0099s`
- VPS probe confirmed `clist/get` returns commodity, bond, and FX data for explicit `i:<secid>` lists while the single-symbol stock path can disconnect
- VPS `draw_future_img()` validation after deploy returned non-empty sections: commodity `9`, bond `6`, FX `8`; generated `bytes` result length `258789`; total validation time `1.761s`, draw phase `1.529s`
- `systemctl restart gsuid`, `systemctl is-active gsuid`, and `journalctl -u gsuid -n 80` confirmed the service is active and loaded without SayuStock syntax/runtime startup errors

## 2026-05-07 all-weather commodity and Japan bond coverage

User feedback:

- the commodity panel should include London gold/silver/copper and WTI explicitly
- the bond panel should include Japan yields, not only China and US yields

Fix in this patch:

- add London gold `122.XAU`, London silver `122.XAG`, and London copper `109.LCPT` to the all-weather commodity universe
- relabel `102.CL00Y` from generic `NYMEX原油` to explicit `WTI原油`
- switch Brent to Eastmoney's current continuous futures code `112.B00Y`
- keep COMEX gold/silver/copper, natural gas, platinum, and selected domestic commodity futures
- add Japan 30Y/10Y/2Y display slots in the bond universe
- update TradingEconomics Japan-yield scraping to return Chinese display names for Japan 30Y/10Y/2Y
- merge Japan yield data back into the all-weather bond section before rendering

Validation:

- `python -m py_compile SayuStock/utils/constant.py SayuStock/stock_info/get_jp_data.py SayuStock/stock_info/draw_future.py`
- local `draw_future_img()` enriched simulation rendered London gold/silver/copper, WTI, Brent, and Japan 30Y/10Y/2Y; image size `900x1295`, elapsed `0.0077s`
- VPS validation after deploy returned commodity count `13` including London gold/silver/copper, WTI, and Brent
- VPS validation returned bond count `9` including Japan 30Y/10Y/2Y; generated image bytes length `294922`; total validation time `1.867s`, draw phase `1.348s`

## 2026-05-07 China market color convention and all-weather layout pass

User feedback:

- `全天候` and `大盘概览` must follow China market colors: red means up, green means down
- the enlarged all-weather asset universe needed a tighter layout

Fix in this patch:

- flip the shared compact `draw_block()` card colors so positive changes render red and negative changes render green
- render flat/zero changes in a neutral gray instead of incorrectly treating them as an up move
- fix the `calculate_alpha()` negative threshold guard so near-zero changes remain neutral
- tighten the all-weather header, avoid title/status overlap, and place the enlarged asset universe in rounded section panels with asset counts
- keep the existing streaming `curr_y` layout and dynamic crop so expanded commodities, bonds, FX, and crypto remain fully visible without a bottom black tail

Validation:

- `python -m py_compile SayuStock/stock_info/draw_info.py SayuStock/stock_info/draw_future.py`
- local isolated `draw_block()` pixel probe returned up `(239, 68, 68)`, down `(34, 197, 94)`, flat `(96, 100, 118)`
- local all-weather stub render covered 16 global indices, 14 commodities, 11 bonds/yields, 8 FX pairs, and 4 crypto cards; generated image size `900x2235`, elapsed `0.086s`

## 2026-05-07 market overview turnover robustness

User feedback:

- `大盘概览` turnover / volume display should be repaired as much as possible

Root cause:

- the existing `calculate_difference()` grouped intraday trend rows by day-of-month only, which is fragile around month boundaries
- it only searched back four calendar days, so long holidays could make the market overview show zero or stale turnover
- `get_hours_from_em()` assumed Eastmoney always returned a non-empty `data.trends` list, so malformed responses could break the volume panel

Fix in this patch:

- group trend rows by full trading date instead of just day number
- select the latest available trading day not later than the adjusted target day, which handles weekends and longer holidays better
- keep the correct `trends2` semantics: `f57` is per-minute turnover, so daily/current turnover is still the sum of all rows for that trading day
- compare against the previous trading day up to the same latest intraday timestamp for a better `放量` / `缩量` value
- add defensive validation around empty or malformed `data.trends`
- when the VPS cannot reach both `trends2` index endpoints, fall back to the more stable `clist/get` snapshot for current Shanghai + Shenzhen turnover
- when only the snapshot fallback is available, render the volume delta as `量差: 暂缺` instead of a misleading zero shrinkage value
- add a short in-process cooldown after `trends2` turnover failures so repeated market-overview commands use the snapshot immediately instead of repeatedly paying the slow failing path

Validation:

- `python -m py_compile SayuStock/utils/stock/utils.py SayuStock/utils/stock/request.py SayuStock/stock_info/draw_info.py`
- isolated live Eastmoney trends probe for China midday `2026-05-07` returned Shanghai current turnover `864218308640.0`, same-time diff `-77502786416.0`; Shenzhen current turnover `1118236505408.0`, same-time diff `-20099117344.0`
- local `draw_info_img()` stub render completed with image size `1700x2860`, elapsed `0.2011s`

## 2026-05-08 all-weather OLED terminal UI refresh

User feedback:

- the `全天候` image works but the previous Gemini-designed UI looked ugly

Fix in this patch:

- redesign only the all-weather rendering layer; keep data fetch, cache, section ordering, and asset coverage unchanged
- replace the older flat black cards with an OLED-style finance terminal dashboard
- add a compact header with live time and explicit China color legend: red up, green down
- draw each section as a darker rounded panel with subtle accent rail, section stats, and asset count pill
- replace the shared compact cards with purpose-built all-weather cards using tighter spacing, price/diff pill, code, and compact amount labels
- flatten the final RGBA image over the dark background so grid/glow effects do not leave transparent artifacts

Validation:

- `python -m py_compile SayuStock/stock_info/draw_future.py`
- local all-weather stub render covered 16 global indices, 14 commodities, 11 bonds/yields, 8 FX pairs, and 4 crypto cards; generated image size `900x2340`, elapsed `0.1516s`
- preview artifact: `%LOCALAPPDATA%/Temp/sayustock_all_weather_ui_v4_flat.png`
