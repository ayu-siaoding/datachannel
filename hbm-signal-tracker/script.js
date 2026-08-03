// HBM 核心逻辑跟踪看板
// 数据来源：用户整理的「HBM 核心逻辑失效【必须卖出】双大类信号清单」

const SIGNALS = {
  fatal: [
    {
      id: "fatal-1",
      title: "英伟达官宣下一代旗舰 GPU 取消绑定式 HBM 架构",
      desc: "Rubin 之后的 Feynman 架构，完全改用片上超大 SRAM + 远端共享内存池，单颗 GPU 不再堆叠 HBM 堆栈；只有推理低端芯片保留少量 HBM。一旦旗舰训练卡砍掉 HBM，三巨头 70% 以上高毛利业务直接崩塌。",
    },
    {
      id: "fatal-2",
      title: "GDDR8 / 新型分布式内存完成带宽反超",
      desc: "低成本宽位 GDDR 方案在 12.8T Scale-up 带宽下，功耗、延迟全面追上 HBM；云厂商批量切换低成本方案，HBM 溢价彻底归零。",
    },
    {
      id: "fatal-3",
      title: "共封装光引擎（CPO）内置内存，替代外置 HBM",
      desc: "CPO 光芯片直接集成存储单元，GPU 不再需要外接堆叠内存，堆叠工艺彻底失去不可替代性。",
    },
    {
      id: "fatal-4",
      title: "长鑫 / 国内厂商量产对标 HBM5 的成熟产品",
      desc: "全球 HBM 寡头格局被打破，供给彻底过剩，HBM 毛利率从 70%+ 跌到普通 DRAM 的 15% 以内。",
    },
  ],
  cyclical: [
    {
      id: "cyclical-1",
      title: "HBM 长协订单开始大规模取消",
      desc: "云厂原本锁到 2027-2028 年的多年框架订单，出现批量下调采购量；这是比现货涨价更先行的信号。",
    },
    {
      id: "cyclical-2",
      title: "DRAM/NAND 库存周数从 3-4 周低位跳升至 12 周以上",
      desc: "存储周期铁律：库存见底是牛市起点，库存重回高位是熊市起点；三巨头被迫减产降价去库存，利润连续两个季度环比下滑。",
    },
    {
      id: "cyclical-3",
      title: "HBM 合约价格连续 2 个月环比涨幅低于 3%，由涨转跌",
      desc: "只要涨价动能熄火，存储股会提前 1 个季度见顶；哪怕销量还在涨，估值也会快速杀跌。",
    },
    {
      id: "cyclical-4",
      title: "三家原厂大幅上调 HBM 资本开支，疯狂新建堆叠产线",
      desc: "所有厂商集体扩产，2 年后必然迎来供给过剩；历史上每一轮存储大跌，都始于集体扩产。",
    },
  ],
  safe: [
    {
      id: "safe-1",
      title: "柜内本地 SSD、普通 SOCAMM 内存减配",
      desc: "正常架构重构，不影响 HBM。",
    },
    {
      id: "safe-2",
      title: "特供版芯片改用 GDDR 规避出口管制",
      desc: "仅限中国低端特供，全球旗舰依旧标配 HBM。",
    },
    {
      id: "safe-3",
      title: "单季度利润略低于市场预期",
      desc: "情绪短期下跌，不改长期刚需。",
    },
  ],
};

const STORAGE_KEY = "hbm-signal-tracker:checked";

function loadChecked() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (e) {
    return {};
  }
}

function saveChecked(checked) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(checked));
}

let checked = loadChecked();

function renderList(groupKey, listElId) {
  const listEl = document.getElementById(listElId);
  listEl.innerHTML = "";
  SIGNALS[groupKey].forEach((signal) => {
    const li = document.createElement("li");
    li.className = "signal-item";
    li.dataset.id = signal.id;

    if (groupKey === "safe") {
      li.innerHTML = `
        <div class="signal-text">
          <div class="signal-title">${signal.title}</div>
          <div class="signal-desc">${signal.desc}</div>
        </div>
      `;
    } else {
      const isChecked = !!checked[signal.id];
      if (isChecked) li.classList.add("checked");
      li.innerHTML = `
        <input type="checkbox" class="signal-checkbox" ${isChecked ? "checked" : ""} />
        <div class="signal-text">
          <div class="signal-title">${signal.title}</div>
          <div class="signal-desc">${signal.desc}</div>
        </div>
      `;
      const checkbox = li.querySelector(".signal-checkbox");
      const toggle = () => {
        checkbox.checked = !checkbox.checked;
        checked[signal.id] = checkbox.checked;
        li.classList.toggle("checked", checkbox.checked);
        saveChecked(checked);
        updateVerdict();
      };
      checkbox.addEventListener("click", (e) => {
        e.stopPropagation();
        checked[signal.id] = checkbox.checked;
        li.classList.toggle("checked", checkbox.checked);
        saveChecked(checked);
        updateVerdict();
      });
      li.addEventListener("click", (e) => {
        if (e.target !== checkbox) toggle();
      });
    }

    listEl.appendChild(li);
  });
}

function anyChecked(groupKey) {
  return SIGNALS[groupKey].some((s) => checked[s.id]);
}

function updateVerdict() {
  const verdict = document.getElementById("verdict");
  const icon = document.getElementById("verdictIcon");
  const title = document.getElementById("verdictTitle");
  const desc = document.getElementById("verdictDesc");

  verdict.classList.remove("state-fatal", "state-cyclical");

  if (anyChecked("fatal")) {
    verdict.classList.add("state-fatal");
    icon.textContent = "🚨";
    title.textContent = "终极致命信号已触发：核心逻辑彻底死掉";
    desc.textContent = "HBM 刚需被推翻，建议长期清仓海力士 / 三星 / 美光。";
  } else if (anyChecked("cyclical")) {
    verdict.classList.add("state-cyclical");
    icon.textContent = "⚠️";
    title.textContent = "周期见顶信号已触发：本轮行情结束";
    desc.textContent = "技术路线未变，但景气周期走完，建议阶段性减持存储三巨头。";
  } else {
    icon.textContent = "✅";
    title.textContent = "核心逻辑健在";
    desc.textContent = "尚未触发任何卖出信号，继续持有并保持跟踪。";
  }
}

document.getElementById("resetBtn").addEventListener("click", () => {
  checked = {};
  saveChecked(checked);
  renderList("fatal", "fatalList");
  renderList("cyclical", "cyclicalList");
  updateVerdict();
});

renderList("fatal", "fatalList");
renderList("cyclical", "cyclicalList");
renderList("safe", "safeList");
updateVerdict();
