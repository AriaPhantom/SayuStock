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
