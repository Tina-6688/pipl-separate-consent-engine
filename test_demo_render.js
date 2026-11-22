// demo.html 渲染冒烟测试
// 用最小 DOM 桩 + node 的 vm，把页面里的 buildNav / showCase 真跑一遍
// 目的：不用打开浏览器也能发现「渲染时抛错」「输出里出现 undefined」
//
// 用法: node test_demo_render.js   （退出码 0=通过 1=失败）
// 报告: _demo_render_report.txt
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('demo.html', 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.log('FAIL 找不到 script'); process.exit(1); }
const js = m[1];

function mkEl(id) {
  return {
    id, innerHTML: '', textContent: '',
    dataset: {},
    classList: { toggle() {}, add() {}, remove() {} },
    addEventListener() {},
    querySelectorAll() { return []; },
    style: {},
  };
}

const els = {};
const document = {
  getElementById(id) { return els[id] || (els[id] = mkEl(id)); },
  querySelectorAll() { return []; },
  createElement() { return mkEl('x'); },
};
const window = { scrollTo() {} };
const sandbox = { document, window, console, JSON };
vm.createContext(sandbox);

// vm 里 top-level const 不会挂到全局，显式导出一次
const jsWithExport = js + "\n;globalThis.__DATA = DATA; globalThis.__showCase = showCase; globalThis.__buildNav = buildNav;";

let loadErr = null;
try {
  vm.runInContext(jsWithExport, sandbox);
} catch (e) {
  loadErr = e.message;
}

const out = [];
if (loadErr) {
  out.push('FAIL 脚本执行出错: ' + loadErr);
  console.log(out.join('\n'));
  fs.writeFileSync('_demo_render_report.txt', out.join('\n'), 'utf8');
  process.exit(1);
}

const DATA = sandbox.__DATA;
out.push('DATA.cases = ' + DATA.cases.length);
out.push('DATA.rules = ' + Object.keys(DATA.rules).length);
out.push('');

let ok = 0;
const bad = [];
for (const c of DATA.cases) {
  try {
    sandbox.__showCase(c.id);
    const inner = document.getElementById('main').innerHTML;
    if (!inner || inner.length < 200) {
      bad.push(c.id + ': 输出过短 (' + (inner ? inner.length : 0) + ' 字符)');
    } else if (inner.indexOf('undefined') >= 0) {
      bad.push(c.id + ': 输出里出现 undefined');
    } else {
      ok++;
    }
  } catch (e) {
    bad.push(c.id + ': ' + e.message);
  }
}

out.push('渲染成功: ' + ok + ' / ' + DATA.cases.length);
if (bad.length) {
  out.push('失败 ' + bad.length + ' 条：');
  bad.forEach(b => out.push('  - ' + b));
} else {
  out.push('全部场景渲染无异常');
}

// 抽查：某个场景是否真的含关键内容
sandbox.__showCase('S4');
const s4 = document.getElementById('main').innerHTML;
out.push('');
out.push('S4 页面含"境外接收方" : ' + (s4.indexOf('境外接收方') >= 0));
out.push('S4 页面含"单独同意"   : ' + (s4.indexOf('单独同意') >= 0));
out.push('S4 页面含"依据条文"   : ' + (s4.indexOf('依据条文') >= 0));

sandbox.__showCase('S14');
const s14 = document.getElementById('main').innerHTML;
out.push('S14 页面含"未覆盖"    : ' + (s14.indexOf('未覆盖') >= 0));
out.push('S14 页面含"无法判定"  : ' + (s14.indexOf('无法判定') >= 0));

const text = out.join('\n');
console.log(text);
fs.writeFileSync('_demo_render_report.txt', text, 'utf8');
const failed = bad.length > 0;
process.exit(failed ? 1 : 0);