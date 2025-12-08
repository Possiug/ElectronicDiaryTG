// ============ Навигация по вкладкам ============

const nav = document.getElementById('topnav');

function markTab() {
  const hash = location.hash || '#dz';
  // Если открыта страница предмета (#sub-...), подсвечиваем "Предметы"
  const effective = hash.startsWith('#sub-') ? '#subjects' : hash;

  nav.querySelectorAll('a').forEach(a => {
    a.classList.toggle('active', a.getAttribute('href') === effective);
  });
}

window.addEventListener('hashchange', markTab);
markTab();

// ============ Данные из бэка ============

const DATA     = window.DIARY_DATA || { student: {}, periods: [], homework: [] };
const PERIODS  = DATA.periods  || [];
const HOMEWORK = DATA.homework || [];

// ============ Элементы DOM ============

const qSel            = document.getElementById('quarterSel');
const qLabel          = document.getElementById('qLabel');
const gradesBody      = document.getElementById('gradesBody');
const summaryBody     = document.getElementById('summaryBody');
const summaryQLabel   = document.getElementById('summaryQLabel');
const subjectsGrid    = document.getElementById('subjectsGrid');
const subjectSections = document.getElementById('subjectSections');
const dzBody          = document.getElementById('dzBody');

// ============ Хелперы ============

function qText(q) {
  return `${q} четверть`;
}

function gradeClass(n) {
  const g = Number(n);
  if (g >= 4.5) return 'g5';
  if (g >= 3.5) return 'g4';
  if (g >= 2.5) return 'g3';
  if (g >= 1.5) return 'g2';
  return 'g1';
}

function getPeriod(num) {
  return PERIODS.find(p => String(p.number) === String(num));
}

// ============ Работа с четвертью (select) ============

function loadQuarter() {
  const saved = localStorage.getItem('selectedQuarter');
  if (saved) qSel.value = saved;
  updateQuarterUI();
}

function saveQuarter() {
  localStorage.setItem('selectedQuarter', qSel.value);
}

qSel.addEventListener('change', () => {
  saveQuarter();
  updateQuarterUI();
});

// ============ Итоговые оценки (вкладка "Итоговые оценки") ============

function buildQuarterSummary(quarter) {
  gradesBody.innerHTML = '';
  if (qLabel) qLabel.textContent = qText(quarter);

  const p = getPeriod(quarter);
  if (!p) {
    gradesBody.innerHTML = `<tr><td colspan="3">Нет данных за выбранную четверть</td></tr>`;
    return;
  }

  (p.subjects || []).forEach(sub => {
    const tr = document.createElement('tr');

    const tdSub = document.createElement('td');
    const tdAvg = document.createElement('td');
    const tdFin = document.createElement('td');

    tdSub.textContent = sub.subject_name;

    // ===== СРЕДНИЙ БАЛЛ (цветной бейджик) =====
    if (sub.avg != null) {
      const avgNum = Number(sub.avg);
      let cls;

      if (avgNum >= 4.5) cls = "avg-g5";
      else if (avgNum >= 3.5) cls = "avg-g4";
      else if (avgNum >= 2.5) cls = "avg-g3";
      else if (avgNum >= 1.5) cls = "avg-g2";
      else cls = "avg-g1";

      const spanAvg = document.createElement('span');
      spanAvg.className = cls;
      spanAvg.textContent = avgNum.toFixed(2);

      tdAvg.appendChild(spanAvg);
    } else {
      const span = document.createElement('span');
      span.className = 'avg-none';
      span.textContent = '--';
      tdAvg.appendChild(span);
    }

    // ===== ИТОГОВАЯ ОЦЕНКА (четвертная) =====
    if (sub.final_mark != null) {
      const fin = Number(sub.final_mark);
      const spanFin = document.createElement('span');
      spanFin.className = 'grade ' + gradeClass(fin);
      spanFin.textContent = String(fin);
      tdFin.appendChild(spanFin);
    } else {
      const spanFin = document.createElement('span');
      spanFin.className = 'grade-none';
      spanFin.textContent = '--';
      tdFin.appendChild(spanFin);
    }

    tr.appendChild(tdSub);
    tr.appendChild(tdAvg);
    tr.appendChild(tdFin);
    gradesBody.appendChild(tr);
  });

  if (!gradesBody.children.length) {
    gradesBody.innerHTML = `<tr><td colspan="3">Нет предметов для отображения</td></tr>`;
  }
}

// ============ Общая сводка (вкладка "Общая сводка") ============

function buildSummary(quarter) {
  if (!summaryBody) return;
  summaryBody.innerHTML = '';
  if (summaryQLabel) summaryQLabel.textContent = qText(quarter);

  const p = getPeriod(quarter);
  if (!p) {
    summaryBody.innerHTML = `<tr><td colspan="3">Нет данных за выбранную четверть</td></tr>`;
    return;
  }

  (p.subjects || []).forEach(sub => {
    const tr = document.createElement('tr');

    const tdSub   = document.createElement('td');
    const tdMarks = document.createElement('td');
    const tdAvg   = document.createElement('td');

    tdSub.textContent = sub.subject_name;

    const marks = sub.marks || [];
    if (!marks.length) {
      tdMarks.textContent = '—';
      tdAvg.textContent   = '—';
    } else {
      let sum = 0;
      let count = 0;

      marks.forEach(m => {
        if (!m.value) return;
        sum   += m.value;
        count += 1;

        const span = document.createElement('span');
        span.className = 'grade ' + gradeClass(m.value);
        span.textContent = String(m.value);
        span.style.marginRight = '4px';
        tdMarks.appendChild(span);
      });

      if (!count) {
        tdMarks.textContent = '—';
        tdAvg.textContent   = '—';
      } else {
        const avg = (sum / count).toFixed(2);
        tdAvg.textContent = avg;
      }
    }

    tr.appendChild(tdSub);
    tr.appendChild(tdMarks);
    tr.appendChild(tdAvg);
    summaryBody.appendChild(tr);
  });

  if (!summaryBody.children.length) {
    summaryBody.innerHTML = `<tr><td colspan="3">Нет предметов для отображения</td></tr>`;
  }
}

// ============ Список предметов и страницы ============

function collectSubjects() {
  const map = new Map();
  PERIODS.forEach(p => {
    (p.subjects || []).forEach(s => {
      if (!map.has(s.subject_shr)) {
        map.set(s.subject_shr, s.subject_name);
      }
    });
  });
  return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
}

function renderSubjects() {
  subjectsGrid.innerHTML = '';
  subjectSections.innerHTML = '';

  const subjects = collectSubjects();

  subjects.forEach(sub => {
    // карточка в "Предметах"
    const card = document.createElement('div');
    card.className = 'subject';
    card.innerHTML = `
      <b>${sub.name}</b>
      <a href="#sub-${sub.id}">Перейти</a>
    `;
    subjectsGrid.appendChild(card);

    // отдельная страница предмета + блок "Последнее ДЗ"
    const sec = document.createElement('section');
    sec.id = `sub-${sub.id}`;
    sec.innerHTML = `
      <div class="wrap">
        <a class="back" href="#subjects">← Назад к предметам</a>
        <h2>${sub.name}</h2>

        <div class="card">
          <div class="muted" id="sub-${sub.id}-info"></div>
          <table>
            <thead>
              <tr><th class="col-date">Дата</th><th>Оценка</th><th>Значение</th><th>Вес</th></tr>
            </thead>
            <tbody id="sub-${sub.id}-tbody"></tbody>
          </table>
          <p class="avg">Средний балл:
            <span class="grade" id="avg-${sub.id}">—</span>
          </p>
        </div>

        <div class="card last-hw-card" id="last-hw-${sub.id}">
          <div class="last-hw-title">Последнее ДЗ</div>
          <div class="last-hw-date"  id="last-hw-${sub.id}-date">—</div>
          <div class="last-hw-text"  id="last-hw-${sub.id}-text">Нет данных</div>
          <div class="last-hw-files" id="last-hw-${sub.id}-files"></div>
        </div>
      </div>
    `;
    subjectSections.appendChild(sec);
  });
}


function updateSubjectPages(quarter) {
  const p = getPeriod(quarter);
  const subjects = collectSubjects();

  subjects.forEach(sub => {
    const info    = document.getElementById(`sub-${sub.id}-info`);
    const tbody   = document.getElementById(`sub-${sub.id}-tbody`);
    const avgSpan = document.getElementById(`avg-${sub.id}`);

    if (!info || !tbody || !avgSpan) return;

    if (!p) {
      info.textContent   = 'Нет данных за выбранную четверть.';
      tbody.innerHTML    = '';
      avgSpan.textContent= '—';
      avgSpan.className  = 'grade';
      return;
    }

    info.textContent = `Четверть ${p.number}: ${p.date_from} → ${p.date_to}`;
    tbody.innerHTML = '';

    const subjData = (p.subjects || []).find(s => s.subject_shr === sub.id);

    if (!subjData || !subjData.marks || !subjData.marks.length) {
      tbody.innerHTML     = '<tr><td colspan="4">Нет оценок за эту четверть.</td></tr>';
      avgSpan.textContent = '—';
      avgSpan.className   = 'grade';
      return;
    }

    subjData.marks.forEach(m => {
      const tr = document.createElement('tr');
      const cls = m.value ? gradeClass(m.value) : '';
      tr.innerHTML = `
        <td>${m.date}</td>
        <td><span class="grade ${cls}">${m.char}</span></td>
        <td>${m.value}</td>
        <td>${m.cost}</td>
      `;
      tbody.appendChild(tr);
    });

    if (subjData.avg == null) {
      avgSpan.textContent = '—';
      avgSpan.className   = 'grade';
    } else {
      const finAvg = Number(subjData.avg);
      avgSpan.textContent = String(finAvg);
      avgSpan.className   = 'grade ' + gradeClass(finAvg);
    }
  });
}

// ============ Домашка (вкладка "ДЗ") ============

function renderHomework() {
  if (!dzBody) return;

  dzBody.innerHTML = '';

  // HOMEWORK: [ { subject_name, items:[{date,text,files:[{hash,name}]}] }, ... ]
  HOMEWORK.forEach(block => {
    const subjectName = block.subject_name;
    const items = block.items || [];

    if (!items.length) return;

    items.forEach(hw => {
      const tr = document.createElement('tr');

      const tdSub  = document.createElement('td');
      const tdText = document.createElement('td');
      const tdDate = document.createElement('td');

      tdSub.textContent  = subjectName;
      tdDate.classList.add("col-date");

      tdDate.textContent = hw.date;

      let textHtml = hw.text || '';
      const files  = hw.files || [];

      if (files.length) {
        const filesLinks = files.map(f => {
          // ссылка на бота с файлом (как в боте: qfile{hash})
          const url = `https://t.me/pss_ednevnik_bot?start=qfile${f.hash}`;
          return `<a href="${url}" target="_blank">${f.name}</a>`;
        }).join(', ');
        textHtml += (textHtml ? '<br>' : '') + `<span class="muted">Файлы: ${filesLinks}</span>`;
      }

      tdText.innerHTML = textHtml || '—';

      tr.appendChild(tdSub);
      tr.appendChild(tdText);
      tr.appendChild(tdDate);
      dzBody.appendChild(tr);
    });
  });

  if (!dzBody.children.length) {
    dzBody.innerHTML = `
      <tr><td colspan="3">На ближайшие дни домашних заданий в дневнике нет.</td></tr>
    `;
  }
}


function fillLastHomework(quarter) {
  const subjects = collectSubjects();

  subjects.forEach(sub => {
    const block = document.getElementById(`last-hw-${sub.id}`);
    if (!block) return;

    const dDate  = document.getElementById(`last-hw-${sub.id}-date`);
    const dText  = document.getElementById(`last-hw-${sub.id}-text`);
    const dFiles = document.getElementById(`last-hw-${sub.id}-files`);

    // ищем домашку этого предмета
    const hwBlock = HOMEWORK.find(x => x.subject_shr === sub.id);

    if (!hwBlock || !hwBlock.items || !hwBlock.items.length) {
      dDate.textContent = '—';
      dText.textContent = 'Нет данных';
      dFiles.innerHTML = '';
      return;
    }

    // берём самое свежее
    const last = hwBlock.items[0];

    dDate.textContent = last.date || '—';
    dText.textContent = last.text || '—';

    if (last.files && last.files.length) {
      dFiles.innerHTML = last.files.map(f => {
        const url = `https://t.me/pss_ednevnik_bot?start=qfile${f.hash}`;
        return `<a href="${url}" target="_blank">${f.name}</a>`;
      }).join('<br>');
    } else {
      dFiles.innerHTML = '';
    }
  });
}

// ============ Обновление при смене четверти ============

function updateQuarterUI() {
  const q = qSel.value;
  buildQuarterSummary(q); // Итоговые оценки
  if (summaryBody) buildSummary(q); // Общая сводка (если раздел есть)
  updateSubjectPages(q); // Страницы предметов
    fillLastHomework(q); // Последняя домашка по предметам
}

// ============ INIT ============
renderSubjects();
renderHomework();
loadQuarter();
fillLastHomework(qSel.value);