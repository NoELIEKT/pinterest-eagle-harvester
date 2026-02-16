const logEl = document.getElementById('log');
const urlsEl = document.getElementById('urls');
const apiBaseEl = document.getElementById('apiBase');
const tokenEl = document.getElementById('token');
const folderIdEl = document.getElementById('folderId');
const tagsEl = document.getElementById('tags');

function log(msg) {
  const now = new Date().toLocaleTimeString();
  logEl.textContent += `[${now}] ${msg}\n`;
  logEl.scrollTop = logEl.scrollHeight;
}

function parseLines(text) {
  return text
    .split(/\r?\n/)
    .map((v) => v.trim())
    .filter(Boolean);
}

function isPinterestPinUrl(url) {
  return /pinterest\.[^/]+\/pin\//i.test(url);
}

function normalizePinImage(url) {
  if (!url) return '';
  return url.replace(/\/\d+x\//, '/originals/');
}

async function extractImageFromPin(pinUrl) {
  const r = await fetch(pinUrl, { method: 'GET' });
  const html = await r.text();

  const m1 = html.match(/<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i);
  const m2 = html.match(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']/i);
  const image = (m1 && m1[1]) || (m2 && m2[1]) || '';
  return normalizePinImage(image);
}

async function addToEagle({ imageUrl, sourceUrl, keywordTags }) {
  const apiBase = apiBaseEl.value.trim().replace(/\/$/, '');
  const token = tokenEl.value.trim();
  const folderId = folderIdEl.value.trim();
  const baseTags = parseLines(tagsEl.value.replace(/,/g, '\n'));

  const body = {
    url: imageUrl,
    name: `pinterest_${Date.now()}`,
    website: sourceUrl || imageUrl,
    tags: [...new Set([...baseTags, ...keywordTags])],
  };

  if (token) body.token = token;
  if (folderId) body.folderId = folderId;

  const res = await fetch(`${apiBase}/api/item/addFromURL`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return data;
}

async function extractPinsOnly() {
  const lines = parseLines(urlsEl.value);
  if (!lines.length) return log('URL 목록이 비어있습니다.');

  const out = [];
  let i = 0;
  for (const u of lines) {
    i += 1;
    try {
      if (isPinterestPinUrl(u)) {
        log(`(${i}/${lines.length}) 핀 분석: ${u}`);
        const img = await extractImageFromPin(u);
        if (img) {
          out.push(img);
          log(`  -> 이미지 추출 성공`);
        } else {
          log(`  -> 실패(og:image 없음)`);
        }
      } else {
        out.push(u);
      }
    } catch (e) {
      log(`  -> 오류: ${e.message}`);
    }
  }

  urlsEl.value = out.join('\n');
  log(`완료: ${out.length}개 URL 준비됨`);
}

async function importAll() {
  const lines = parseLines(urlsEl.value);
  if (!lines.length) return log('가져올 URL이 없습니다.');

  let ok = 0;
  let fail = 0;

  for (let i = 0; i < lines.length; i++) {
    const u = lines[i];
    try {
      let imageUrl = u;
      let sourceUrl = u;

      if (isPinterestPinUrl(u)) {
        log(`(${i + 1}/${lines.length}) 핀에서 이미지 추출 중...`);
        imageUrl = await extractImageFromPin(u);
        if (!imageUrl) throw new Error('핀에서 이미지 추출 실패');
      }

      const data = await addToEagle({ imageUrl, sourceUrl, keywordTags: ['pinterest'] });
      if (data?.status === 'success') {
        ok += 1;
        log(`  ✅ 가져오기 성공`);
      } else {
        fail += 1;
        log(`  ❌ 실패: ${JSON.stringify(data)}`);
      }
    } catch (e) {
      fail += 1;
      log(`  ❌ 오류: ${e.message}`);
    }

    await new Promise((r) => setTimeout(r, 300));
  }

  log(`끝. 성공 ${ok} / 실패 ${fail}`);
}

document.getElementById('extractBtn').addEventListener('click', extractPinsOnly);
document.getElementById('importBtn').addEventListener('click', importAll);

log('준비 완료. Pinterest URL 또는 이미지 URL을 붙여넣으세요.');
