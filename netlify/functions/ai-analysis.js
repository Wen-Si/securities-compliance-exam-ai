/**
 * AI 考情分析 Netlify Function
 * 调用智谱 GLM-4.5-Flash 对考生本次考试数据进行智能分析并给出学习建议。
 * API Key 通过 Netlify 环境变量 ZHIPU_API_KEY 注入，不进入仓库。
 */
const ZHIPU_API_URL = 'https://open.bigmodel.cn/api/paas/v4/chat/completions';
const MODEL = 'glm-4.5-flash';

function buildPrompt(data) {
  const score = data.score;
  const total = data.total;
  const correct = data.correct;
  const ts = data.typeStats || {};
  const cats = data.catStats || [];
  const wrongs = data.wrongSamples || [];

  const typeLines = [
    '  - 单选题：' + (ts.sc1 != null ? ts.sc1 : 0) + '/' + (ts.st1 != null ? ts.st1 : 0) +
      '（正确率 ' + (ts.s1Rate != null ? ts.s1Rate : 0) + '%）',
    '  - 多选题：' + (ts.sc2 != null ? ts.sc2 : 0) + '/' + (ts.st2 != null ? ts.st2 : 0) +
      '（正确率 ' + (ts.s2Rate != null ? ts.s2Rate : 0) + '%）',
    '  - 判断题：' + (ts.sc3 != null ? ts.sc3 : 0) + '/' + (ts.st3 != null ? ts.st3 : 0) +
      '（正确率 ' + (ts.s3Rate != null ? ts.s3Rate : 0) + '%）'
  ].join('\n');

  const catLines = cats.length
    ? cats.map(function (c) {
        return '  - ' + c.name + '：' + c.correct + '/' + c.total + '（正确率 ' + c.pct + '%）';
      }).join('\n')
    : '  - 无分类统计数据';

  const wrongLines = wrongs.length
    ? wrongs.map(function (w, i) {
        return (i + 1) + '. [' + (w.category || '综合') + '] ' + w.q;
      }).join('\n')
    : '  - 无错题（本次全部答对）';

  return [
    '你是证券业风控合规考试的资深培训专家。请根据以下考生本次模拟考试的数据，给出专业的考情分析与下一步学习建议。',
    '',
    '【考试数据】',
    '- 总分：' + score + ' 分（满分100分，60分及格）',
    '- 答对：' + correct + ' / ' + total + ' 题',
    '- 各题型正确率：',
    typeLines,
    '- 各知识模块正确率（已按正确率从低到高排序）：',
    catLines,
    '- 部分错题示例：',
    wrongLines,
    '',
    '【输出要求】',
    '请严格按以下 Markdown 格式输出，使用中文，共四个部分，每部分都要具体、可执行，结合证券合规实务，避免空话套话：',
    '',
    '### 考情总评',
    '用2-4句话点评整体表现：是否及格、整体水平、最突出的优缺点。',
    '',
    '### 薄弱环节分析',
    '针对正确率最低的2-3个知识模块，逐个分析失分原因（结合证券合规实务与法规要点），每个模块2-3句话。',
    '',
    '### 个性化学习建议',
    '给出3-5条针对性学习建议，每条以 "1. "、"2. " 编号开头，包含"建议做什么 + 为什么"，涵盖法规记忆、实务理解、易错点辨析等。',
    '',
    '### 下一步学习计划',
    '给出未来1-2周的学习计划，按"第1天/第2天…"或"每日"形式，具体到每天练习题量与复习模块。'
  ].join('\n');
}

async function callZhipu(prompt) {
  const apiKey = process.env.ZHIPU_API_KEY;
  if (!apiKey) {
    throw new Error('未配置 ZHIPU_API_KEY 环境变量');
  }
  const resp = await fetch(ZHIPU_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer ' + apiKey
    },
    body: JSON.stringify({
      model: MODEL,
      messages: [{ role: 'user', content: prompt }],
      temperature: 0.7,
      max_tokens: 1800
    })
  });

  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error('智谱API错误 ' + resp.status + ': ' + errText.slice(0, 300));
  }
  const data = await resp.json();
  const content =
    data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content;
  if (!content) {
    throw new Error('智谱API返回内容为空');
  }
  return content;
}

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type'
};

function json(statusCode, obj) {
  return {
    statusCode: statusCode,
    headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, CORS_HEADERS),
    body: JSON.stringify(obj)
  };
}

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: CORS_HEADERS, body: '' };
  }
  if (event.httpMethod !== 'POST') {
    return json(405, { ok: false, error: 'Method Not Allowed' });
  }

  let payload;
  try {
    payload = JSON.parse(event.body || '{}');
  } catch (e) {
    return json(400, { ok: false, error: '请求体格式错误' });
  }

  if (payload.score == null || payload.total == null) {
    return json(400, { ok: false, error: '缺少必要的考试数据' });
  }

  try {
    const prompt = buildPrompt(payload);
    const content = await callZhipu(prompt);
    return json(200, { ok: true, content: content });
  } catch (err) {
    return json(500, { ok: false, error: err && err.message ? err.message : String(err) });
  }
};
