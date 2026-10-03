// CrossMind — SPA Application Logic
renderAppNav();

const H = h => $('#v').innerHTML = h;
let CURRENT_DOC = null;
let QUIZ_TIMER = null;
let LEADERBOARD_INTERVAL = null;
let VOICE_RECOGNITION = null;

const esc = s => String(s || '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const emptyCard = (msg, btn) => `<div class="card" style="text-align:center;padding:40px 20px"><p class="mu" style="font-size:18px">${msg}</p>${btn || ''}</div>`;

function route() {
  clearInterval(QUIZ_TIMER);
  clearInterval(LEADERBOARD_INTERVAL);
  
  const hash = location.hash.slice(1) || 'dashboard';
  const parts = hash.split('/');
  const view = parts[0];
  const param = parts[1];

  const role = localStorage.role || 'student';

  if (view === 'dashboard') {
    if (role === 'teacher') teacherDash();
    else studentDash();
  } else if (view === 'classrooms') {
    if (role === 'teacher') teacherClassrooms();
    else studentDash();
  } else if (view === 'classroom') {
    viewClassroom(param);
  } else if (view === 'create-classroom') {
    createClassroomView();
  } else if (view === 'join-classroom') {
    joinClassroomView();
  } else if (view === 'create-quiz') {
    createQuizView();
  } else if (view === 'quiz') {
    playQuizView(param);
  } else if (view === 'live-leaderboard') {
    liveLeaderboardView(param);
  } else if (view === 'performance') {
    studentPerformanceView();
  } else if (view === 'analytics') {
    teacherAnalyticsView(param);
  } else if (view === 'create-crossword') {
    createCrosswordView();
  } else if (view === 'play-crossword') {
    playCrosswordView(param);
  } else if (view === 'history') {
    historyView();
  } else {
    if (role === 'teacher') teacherDash();
    else studentDash();
  }
}

addEventListener('hashchange', route);
route();

// Student Dashboard View
async function studentDash() {
  try {
    const [crosswords, classrooms, perf] = await Promise.all([
      API.f('/crosswords'),
      API.f('/classrooms'),
      API.f('/student/performance')
    ]);

    const completedCw = crosswords.filter(x => x.done);

    H(`
      <div class="dashboard-header">
        <h1>Hello, ${esc(localStorage.name)}! 👋</h1>
        <p class="mu">Welcome to your CrossMind Student Dashboard.</p>
      </div>

      <div class="grid cols-4">
        <div class="card">
          <div class="stat">${perf.quizzes_completed}</div>
          <div class="mu">Quizzes Completed</div>
        </div>
        <div class="card">
          <div class="stat">${perf.average_score}%</div>
          <div class="mu">Avg Quiz Score</div>
        </div>
        <div class="card">
          <div class="stat">${perf.best_score}%</div>
          <div class="mu">Best Quiz Score</div>
        </div>
        <div class="card">
          <div class="stat">#${perf.quizzes_completed ? '3' : '—'}</div>
          <div class="mu">Overall Class Rank</div>
        </div>
      </div>

      <div class="side" style="margin: 20px 0;">
        <a class="btn primary lg" href="#join-classroom">🔑 Join Classroom</a>
        <a class="btn accent lg" href="#create-crossword">🧩 Generate Crossword</a>
        <a class="btn alt lg" href="#performance">📊 View My Performance</a>
      </div>

      <div class="grid cols-2">
        <div class="card">
          <h3>Active Classrooms (${classrooms.length})</h3>
          ${classrooms.length ? `
            <table class="t">
              <thead><tr><th>Classroom</th><th>Teacher</th><th>Students</th><th>Action</th></tr></thead>
              <tbody>
                ${classrooms.map(c => `
                  <tr>
                    <td><b>${esc(c.name)}</b><br><small class="mu">${esc(c.subject)} (${esc(c.division)})</small></td>
                    <td>${esc(c.teacher)}</td>
                    <td>${c.student_count}</td>
                    <td><a class="btn alt" href="#classroom/${c.id}">View</a></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : emptyCard('You have not joined any classrooms yet.', '<a class="btn primary" href="#join-classroom">Join Classroom</a>')}
        </div>

        <div class="card">
          <h3>Recent Crossword Puzzles</h3>
          ${crosswords.length ? `
            <table class="t">
              <thead><tr><th>Topic</th><th>Difficulty</th><th>Score</th><th>Action</th></tr></thead>
              <tbody>
                ${crosswords.slice(0, 5).map(x => `
                  <tr>
                    <td><b>${esc(x.title)}</b></td>
                    <td><span class="tag ${x.difficulty}">${x.difficulty.toUpperCase()}</span></td>
                    <td>${x.score !== null ? x.score + '%' : 'In Progress'}</td>
                    <td><a class="btn primary" href="#play-crossword/${x.id}">Play</a></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : emptyCard('No crosswords generated yet.', '<a class="btn accent" href="#create-crossword">Generate Crossword</a>')}
        </div>
      </div>
    `);
  } catch (e) {
    toast(e.message);
  }
}

// Teacher Dashboard View
async function teacherDash() {
  try {
    const classrooms = await API.f('/classrooms');
    const totalStudents = classrooms.reduce((acc, c) => acc + c.student_count, 0);
    const totalQuizzes = classrooms.reduce((acc, c) => acc + c.quiz_count, 0);

    H(`
      <div class="dashboard-header">
        <h1>Teacher Command Center 👨‍🏫</h1>
        <p class="mu">Manage your classrooms, generate AI quizzes, and monitor live leaderboards.</p>
      </div>

      <div class="grid cols-4">
        <div class="card">
          <div class="stat">${classrooms.length}</div>
          <div class="mu">Active Classrooms</div>
        </div>
        <div class="card">
          <div class="stat">${totalStudents}</div>
          <div class="mu">Total Enrolled Students</div>
        </div>
        <div class="card">
          <div class="stat">${totalQuizzes}</div>
          <div class="mu">Assigned Quizzes</div>
        </div>
        <div class="card">
          <div class="stat">94%</div>
          <div class="mu">Class Participation</div>
        </div>
      </div>

      <div class="side" style="margin: 20px 0;">
        <a class="btn primary lg" href="#create-classroom">➕ Create Classroom</a>
        <a class="btn accent lg" href="#create-quiz">📝 Create Classroom Quiz</a>
        <a class="btn alt lg" href="#create-crossword">🧩 Generate Crossword</a>
      </div>

      <div class="card">
        <h3>My Classrooms</h3>
        ${classrooms.length ? `
          <table class="t">
            <thead><tr><th>Classroom Name</th><th>Subject & Div</th><th>Class Code</th><th>Enrolled Students</th><th>Quizzes</th><th>Actions</th></tr></thead>
            <tbody>
              ${classrooms.map(c => `
                <tr>
                  <td><b>${esc(c.name)}</b></td>
                  <td>${esc(c.subject)} - Div ${esc(c.division)}</td>
                  <td>
                    <span class="code-badge" style="font-size:16px;padding:4px 10px;" onclick="copyText('${c.code}')" title="Click to copy">
                      ${c.code} 📋
                    </span>
                  </td>
                  <td>${c.student_count} students</td>
                  <td>${c.quiz_count} quizzes</td>
                  <td>
                    <a class="btn primary" href="#classroom/${c.id}">Manage</a>
                    <a class="btn alt" href="#analytics/${c.id}">Analytics</a>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        ` : emptyCard('You have not created any classrooms yet.', '<a class="btn primary" href="#create-classroom">Create Classroom Now</a>')}
      </div>
    `);
  } catch (e) {
    toast(e.message);
  }
}

// Create Classroom View
function createClassroomView() {
  H(`
    <div class="card" style="max-width: 650px; margin: 40px auto;">
      <h2>Create New Classroom</h2>
      <p class="mu">Generate a virtual classroom and a shareable classroom code for your students.</p>

      <label>Classroom Name
        <input id="cn" placeholder="e.g. Data Science - TE DS" required>
      </label>

      <label>Subject
        <input id="cs" placeholder="e.g. Data Science / DBMS" required>
      </label>

      <label>Division
        <input id="cd" placeholder="e.g. B" value="A">
      </label>

      <label>Description (Optional)
        <textarea id="cx" rows="3" placeholder="Data Science Semester V Course materials and quizzes"></textarea>
      </label>

      <button class="btn primary lg block" onclick="submitCreateClassroom()">Create Classroom & Generate Code</button>
    </div>
  `);
}

async function submitCreateClassroom() {
  try {
    const data = await API.f('/classrooms', {
      method: 'POST',
      json: {
        name: $('#cn').value,
        subject: $('#cs').value,
        division: $('#cd').value,
        description: $('#cx').value
      }
    });

    toast('Classroom created successfully!');
    location.hash = 'classroom/' + data.id;
  } catch (e) {
    toast(e.message);
  }
}

// Join Classroom View
function joinClassroomView() {
  H(`
    <div class="card" style="max-width: 500px; margin: 40px auto; text-align: center;">
      <h2>Join a Classroom</h2>
      <p class="mu">Enter the 6-character classroom code provided by your teacher.</p>

      <div style="margin: 24px 0;">
        <input id="jcode" placeholder="e.g. DSB472" style="font-size: 24px; text-align: center; text-transform: uppercase; letter-spacing: 4px; font-weight: 700;" maxlength="6">
      </div>

      <button class="btn accent lg block" onclick="submitJoinClassroom()">Join Classroom</button>
      <div id="join-status" style="margin-top: 16px;"></div>
    </div>
  `);
}

async function submitJoinClassroom() {
  const code = $('#jcode').value.trim();
  if (!code) return toast('Please enter a classroom code.');
  try {
    const res = await API.f('/classrooms/join', {
      method: 'POST',
      json: { code }
    });

    $('#join-status').innerHTML = `
      <div class="card" style="background:#DCFCE7;border-color:#86EFAC;color:#15803D;">
        <h3>Successfully Joined! 🎉</h3>
        <p><b>${esc(res.classroom.name)}</b><br>Teacher: ${esc(res.classroom.teacher)} · ${res.classroom.student_count} Students</p>
        <a class="btn primary" href="#classroom/${res.classroom.id}">View Classroom</a>
      </div>
    `;
    toast('Joined classroom successfully!');
  } catch (e) {
    $('#join-status').innerHTML = `<div style="color:var(--bad);font-weight:600;margin-top:12px;">${esc(e.message)}</div>`;
  }
}

// View Classroom Details View
async function viewClassroom(id) {
  try {
    const c = await API.f('/classrooms/' + id);

    let mainContent = '';
    if (c.is_teacher) {
      // Teacher View
      mainContent = `
        <div class="card" style="background: linear-gradient(135deg, rgba(79, 70, 229, 0.08), rgba(124, 58, 237, 0.08));">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;">
            <div>
              <h2>${esc(c.name)}</h2>
              <p class="mu">${esc(c.subject)} — Div ${esc(c.division)} · ${c.student_count} Students</p>
            </div>
            <div>
              <span class="mu" style="font-size:14px;display:block;margin-bottom:4px;">CLASS CODE</span>
              <span class="code-badge" onclick="copyText('${c.code}')" title="Click to copy code">
                ${c.code} 📋
              </span>
            </div>
          </div>
        </div>

        <div class="side" style="margin: 20px 0;">
          <a class="btn primary lg" href="#create-quiz?classroom_id=${c.id}">📝 Create Quiz</a>
          <a class="btn accent lg" href="#create-crossword">🧩 Generate Crossword</a>
          <a class="btn alt lg" href="#analytics/${c.id}">📊 Class Analytics</a>
        </div>

        <div class="card">
          <h3>Classroom Quizzes</h3>
          ${c.quizzes.length ? `
            <table class="t">
              <thead><tr><th>Quiz Title</th><th>Topic</th><th>Questions & Time</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>
                ${c.quizzes.map(q => `
                  <tr>
                    <td><b>${esc(q.title)}</b></td>
                    <td>${esc(q.topic)} (${q.difficulty.toUpperCase()})</td>
                    <td>${q.question_count} Qs · ${q.time_limit} mins</td>
                    <td>
                      ${q.is_active ? '<span class="tag active">● LIVE NOW</span>' : '<span class="tag pending">READY</span>'}
                    </td>
                    <td>
                      ${q.is_active ? `
                        <button class="btn bad" onclick="endQuiz(${q.id}, ${c.id})">End Quiz</button>
                        <a class="btn accent" href="#live-leaderboard/${q.id}">Live Leaderboard</a>
                      ` : `
                        <button class="btn primary" onclick="startQuiz(${q.id}, ${c.id})">Start Live Quiz</button>
                        <a class="btn alt" href="#live-leaderboard/${q.id}">Leaderboard</a>
                      `}
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : emptyCard('No quizzes assigned to this classroom yet.', `<a class="btn primary" href="#create-quiz?classroom_id=${c.id}">Create Quiz</a>`)}
        </div>

        <div class="card">
          <h3>Enrolled Students (${c.students.length})</h3>
          ${c.students.length ? `
            <table class="t">
              <thead><tr><th>Name</th><th>Email</th><th>Action</th></tr></thead>
              <tbody>
                ${c.students.map(st => `
                  <tr>
                    <td><b>${esc(st.name)}</b></td>
                    <td>${esc(st.email)}</td>
                    <td><button class="btn bad" onclick="removeStudent(${c.id}, ${st.id})">Remove</button></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : emptyCard('No students enrolled yet. Share class code: <b>' + c.code + '</b>')}
        </div>
      `;
    } else {
      // Student View
      mainContent = `
        <div class="card">
          <h2>${esc(c.name)}</h2>
          <p class="mu">${esc(c.subject)} — Div ${esc(c.division)} · Teacher: ${esc(c.teacher)} · ${c.student_count} Peers</p>
        </div>

        <div class="card">
          <h3>Available Quizzes</h3>
          ${c.quizzes.length ? `
            <table class="t">
              <thead><tr><th>Quiz Title</th><th>Topic</th><th>Questions</th><th>Time</th><th>My Score</th><th>Action</th></tr></thead>
              <tbody>
                ${c.quizzes.map(q => `
                  <tr>
                    <td><b>${esc(q.title)}</b></td>
                    <td>${esc(q.topic)}</td>
                    <td>${q.question_count} Qs</td>
                    <td>${q.time_limit} mins</td>
                    <td>${q.my_score !== null ? q.my_score + '%' : '—'}</td>
                    <td>
                      ${q.my_status === 'completed' ? `
                        <a class="btn alt" href="#quiz/${q.id}">Review Results</a>
                      ` : (q.is_active ? `
                        <a class="btn primary" href="#quiz/${q.id}">● START QUIZ NOW</a>
                      ` : `
                        <span class="tag pending">Waiting for Teacher</span>
                      `)}
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : emptyCard('No quizzes assigned yet.')}
        </div>
      `;
    }

    H(mainContent);
  } catch (e) {
    toast(e.message);
  }
}

async function startQuiz(quizId, classId) {
  try {
    await API.f(`/quizzes/${quizId}/start`, { method: 'POST' });
    toast('Quiz is now LIVE for all students!');
    viewClassroom(classId);
  } catch (e) {
    toast(e.message);
  }
}

async function endQuiz(quizId, classId) {
  try {
    await API.f(`/quizzes/${quizId}/end`, { method: 'POST' });
    toast('Quiz ended.');
    viewClassroom(classId);
  } catch (e) {
    toast(e.message);
  }
}

async function removeStudent(classId, studentId) {
  if (!confirm('Remove this student from classroom?')) return;
  try {
    await API.f(`/classrooms/${classId}/students/${studentId}`, { method: 'DELETE' });
    toast('Student removed.');
    viewClassroom(classId);
  } catch (e) {
    toast(e.message);
  }
}

function copyText(txt) {
  navigator.clipboard.writeText(txt);
  toast('Classroom code ' + txt + ' copied to clipboard!');
}

// Teacher Quiz Generator View
async function createQuizView() {
  const urlParams = new URLSearchParams(location.hash.split('?')[1] || '');
  const classId = urlParams.get('classroom_id');

  const classrooms = await API.f('/classrooms');

  H(`
    <div class="card" style="max-width: 800px; margin: 20px auto;">
      <h2>Create & Assign AI Quiz</h2>
      <p class="mu">Upload study notes, enter a topic, or dictating material to auto-generate questions using AI/NLP.</p>

      <div class="card" style="background:var(--bg);">
        <h3>1. Target Classroom & Topic</h3>
        <label>Select Classroom
          <select id="qz-class">
            ${classrooms.map(c => `<option value="${c.id}" ${c.id == classId ? 'selected' : ''}>${esc(c.name)} (${esc(c.subject)})</option>`).join('')}
          </select>
        </label>

        <label>Quiz Title
          <input id="qz-title" placeholder="e.g. DBMS Fundamentals Quiz" required>
        </label>

        <label>Topic / Subject
          <input id="qz-topic" placeholder="e.g. Relational Algebra, Machine Learning" required>
        </label>

        <div style="margin: 10px 0;">
          <button class="btn alt" onclick="startVoiceInput('#qz-topic')">🎙 Speak Topic / Prompt</button>
        </div>
      </div>

      <div class="card" style="background:var(--bg);">
        <h3>2. Upload Material or Paste Notes</h3>
        <div id="drop" class="card" style="border-style:dashed;text-align:center;">
          Drop study files here or <input type="file" id="qz-fi" multiple accept=".pdf,.pptx,.docx,.xlsx,.xls,.csv,.txt"><br>
          <small class="mu">Supported: PDF • PPTX • DOCX • XLSX • CSV • TXT</small>
        </div>
        <label>Or Paste Learning Excerpt
          <textarea id="qz-tx" rows="4" placeholder="Paste notes or textbook chapter text here..."></textarea>
        </label>
        <button class="btn accent block" onclick="generateQuizQuestions()">🤖 AI Analyze & Generate Questions</button>
      </div>

      <div id="qz-generated-preview"></div>
    </div>
  `);
}

function startVoiceInput(targetSelector) {
  const R = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!R) return toast('Voice recognition is not supported in this browser.');

  VOICE_RECOGNITION = new R();
  VOICE_RECOGNITION.onresult = e => {
    const text = e.results[0][0].transcript;
    $(targetSelector).value = text;
    toast('Recorded: "' + text + '"');
  };
  VOICE_RECOGNITION.start();
  toast('Listening... Speak your topic or notes now.');
}

async function generateQuizQuestions() {
  toast('Analyzing material... Generating questions...');
  $('#qz-generated-preview').innerHTML = emptyCard('AI is extracting key concepts and generating questions...');

  const f = new FormData();
  [...$('#qz-fi').files].forEach(x => f.append('files', x));
  f.append('text', $('#qz-tx').value);
  f.append('topic', $('#qz-topic').value);

  try {
    let docId = null;
    if ($('#qz-fi').files.length || $('#qz-tx').value.strip()) {
      const docRes = await API.f('/documents/analyze', { method: 'POST', body: f });
      docId = docRes.doc_id;
    }

    const quizRes = await API.f('/quizzes/generate', {
      method: 'POST',
      json: {
        doc_id: docId,
        topic: $('#qz-topic').value || 'Study Notes',
        difficulty: 'medium',
        count: 15,
        question_types: ['mcq', 'true_false', 'msq']
      }
    });

    window.GENERATED_QUESTIONS = quizRes.questions;
    window.GENERATED_DOC_ID = docId;

    $('#qz-generated-preview').innerHTML = `
      <div class="card" style="border-color:var(--p);">
        <h3>3. Quiz Preview (${quizRes.questions.length} Generated Questions)</h3>
        
        <label>Time Limit (Minutes)
          <input id="qz-time" type="number" value="15" min="1" max="180">
        </label>

        <label>Difficulty
          <select id="qz-diff">
            <option value="easy">Easy (Direct definitions)</option>
            <option value="medium" selected>Medium (Conceptual)</option>
            <option value="hard">Hard (Advanced implication)</option>
          </select>
        </label>

        <h4>Sample Generated Questions:</h4>
        <div style="max-height: 250px; overflow-y: auto; background: var(--bg); padding: 12px; border-radius: 8px;">
          ${quizRes.questions.slice(0, 5).map((q, i) => `
            <p><b>Q${i+1} (${q.type.toUpperCase()}):</b> ${esc(q.question)}<br>
            <small class="mu">Answer: ${esc(Array.isArray(q.answer) ? q.answer.join(', ') : q.answer)}</small></p>
          `).join('')}
        </div>

        <button class="btn primary lg block" style="margin-top:16px;" onclick="submitAssignQuiz()">
          🚀 Assign Quiz to Classroom
        </button>
      </div>
    `;
  } catch (e) {
    $('#qz-generated-preview').innerHTML = '';
    toast(e.message);
  }
}

async function submitAssignQuiz() {
  try {
    const data = await API.f('/quizzes', {
      method: 'POST',
      json: {
        classroom_id: +$('#qz-class').value,
        doc_id: window.GENERATED_DOC_ID,
        title: $('#qz-title').value,
        topic: $('#qz-topic').value,
        difficulty: $('#qz-diff').value,
        time_limit: +$('#qz-time').value,
        questions: window.GENERATED_QUESTIONS,
        controls: {
          randomize_questions: true,
          randomize_options: true,
          allow_hints: true,
          show_answers: true,
          show_leaderboard: true,
          leaderboard_privacy: 'full'
        }
      }
    });

    toast('Quiz assigned to classroom successfully!');
    location.hash = 'classroom/' + $('#qz-class').value;
  } catch (e) {
    toast(e.message);
  }
}

// Live Quiz Runner & Review View
async function playQuizView(quizId) {
  try {
    const q = await API.f('/quizzes/' + quizId);

    if (q.submitted) {
      // Show Completed Quiz Results
      const att = q.my_attempt;
      H(`
        <div class="card" style="max-width:800px;margin:20px auto;">
          <h2>Quiz Complete — ${esc(q.title)}</h2>
          <p class="mu">${esc(q.topic)} · ${esc(q.classroom_name)}</p>

          <div class="grid cols-3" style="margin:20px 0;">
            <div class="card" style="text-align:center;">
              <div class="stat">${att.percentage}%</div>
              <div class="mu">Score Percentage</div>
            </div>
            <div class="card" style="text-align:center;">
              <div class="stat">${att.correct_count} / ${q.questions.length}</div>
              <div class="mu">Correct Answers</div>
            </div>
            <div class="card" style="text-align:center;">
              <div class="stat">${Math.floor(att.time_taken_secs / 60)}m ${att.time_taken_secs % 60}s</div>
              <div class="mu">Time Taken</div>
            </div>
          </div>

          <div class="side">
            <a class="btn primary" href="#live-leaderboard/${q.id}">🏆 View Classroom Leaderboard</a>
            <a class="btn alt" href="#classroom/${q.classroom_id}">Return to Classroom</a>
          </div>
        </div>

        <div class="card" style="max-width:800px;margin:20px auto;">
          <h3>Question Review & Learning Explanations</h3>
          ${q.questions.map((item, idx) => {
            const userAns = att.answers[item.id];
            const isCorrect = String(userAns).strip().upper() === String(item.answer).strip().upper();
            return `
              <div class="card" style="border-left: 5px solid ${isCorrect ? 'var(--ok)' : 'var(--bad)'}">
                <b>Q${idx + 1}: ${esc(item.question)}</b>
                <p>
                  Your Answer: <b>${esc(userAns || 'Unanswered')}</b><br>
                  Correct Answer: <b style="color:var(--ok)">${esc(Array.isArray(item.answer) ? item.answer.join(', ') : item.answer)}</b>
                </p>
                <div style="background:var(--bg);padding:10px;border-radius:8px;font-size:14px;" class="mu">
                  💡 <b>Explanation:</b> ${esc(item.explanation)}<br>
                  <small>Source: ${esc(item.source)}</small>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      `);
      return;
    }

    // Active Quiz Execution
    let currentQIdx = 0;
    let answers = {};
    let secsLeft = q.time_limit * 60;
    let timeTakenSecs = 0;

    const renderQuizQuestion = () => {
      const item = q.questions[currentQIdx];
      const selected = answers[item.id];

      let inputHtml = '';
      if (item.type === 'true_false' || item.type === 'mcq') {
        inputHtml = item.options.map(opt => `
          <button class="option-btn ${selected === opt ? 'selected' : ''}" onclick="selectOption('${item.id}', '${esc(opt)}')">
            ${selected === opt ? '🔘' : '⚪'} ${esc(opt)}
          </button>
        `).join('');
      } else if (item.type === 'msq') {
        const selList = Array.isArray(selected) ? selected : [];
        inputHtml = item.options.map(opt => `
          <button class="option-btn ${selList.includes(opt) ? 'selected' : ''}" onclick="toggleMsqOption('${item.id}', '${esc(opt)}')">
            ${selList.includes(opt) ? '☑' : '☐'} ${esc(opt)}
          </button>
        `).join('');
      }

      H(`
        <div class="card" style="max-width:800px;margin:20px auto;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span>Question <b>${currentQIdx + 1}</b> of <b>${q.questions.length}</b></span>
            <span class="code-badge" id="timer-display" style="font-size:18px;padding:4px 12px;">
              ⏱ Timer: ${Math.floor(secsLeft / 60)}:${String(secsLeft % 60).padStart(2, '0')}
            </span>
          </div>

          <div style="margin: 24px 0;">
            <h3 style="font-size:20px;">${esc(item.question)}</h3>
            <div style="margin-top:20px;">
              ${inputHtml}
            </div>
          </div>

          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:30px;">
            <button class="btn alt" ${currentQIdx === 0 ? 'disabled' : ''} onclick="navQuestion(-1)">← Previous</button>
            
            ${item.hint ? `<button class="btn alt" onclick="toast('Hint: ' + '${esc(item.hint)}')">💡 Show Hint</button>` : ''}

            ${currentQIdx === q.questions.length - 1 ? `
              <button class="btn primary lg" onclick="submitActiveQuiz()">Submit Quiz Now</button>
            ` : `
              <button class="btn primary" onclick="navQuestion(1)">Next →</button>
            `}
          </div>
        </div>
      `);
    };

    window.selectOption = (qid, val) => {
      answers[qid] = val;
      renderQuizQuestion();
    };

    window.toggleMsqOption = (qid, val) => {
      let current = answers[qid] || [];
      if (!Array.isArray(current)) current = [];
      if (current.includes(val)) current = current.filter(x => x !== val);
      else current.push(val);
      answers[qid] = current;
      renderQuizQuestion();
    };

    window.navQuestion = (dir) => {
      currentQIdx = Math.max(0, Math.min(q.questions.length - 1, currentQIdx + dir));
      renderQuizQuestion();
    };

    window.submitActiveQuiz = async () => {
      if (!confirm('Are you sure you want to submit your quiz?')) return;
      clearInterval(QUIZ_TIMER);
      try {
        const res = await API.f(`/quizzes/${q.id}/submit`, {
          method: 'POST',
          json: { answers, time_taken_secs: timeTakenSecs }
        });
        toast('Quiz submitted!');
        playQuizView(quizId);
      } catch (e) {
        toast(e.message);
      }
    };

    QUIZ_TIMER = setInterval(() => {
      secsLeft--;
      timeTakenSecs++;
      if (secsLeft <= 0) {
        clearInterval(QUIZ_TIMER);
        toast('Time is up! Submitting quiz automatically...');
        window.submitActiveQuiz();
      } else {
        const tDisp = $('#timer-display');
        if (tDisp) tDisp.textContent = `⏱ Timer: ${Math.floor(secsLeft / 60)}:${String(secsLeft % 60).padStart(2, '0')}`;
      }
    }, 1000);

    renderQuizQuestion();

  } catch (e) {
    toast(e.message);
  }
}

// Live Classroom Leaderboard View
async function liveLeaderboardView(quizId) {
  const fetchLeaderboard = async () => {
    try {
      const data = await API.f(`/quizzes/${quizId}/live-leaderboard`);
      
      const rowsHtml = data.leaderboard.map(item => `
        <tr>
          <td>
            <span class="rank-badge rank-${item.rank}">${item.rank <= 3 ? ['🥇','🥈','🥉'][item.rank-1] : item.rank}</span>
          </td>
          <td><b>${esc(item.student_name)}</b></td>
          <td><b>${item.percentage}%</b> (${item.score}/${item.total})</td>
          <td>${Math.floor(item.time_taken_secs / 60)}m ${item.time_taken_secs % 60}s</td>
          <td><span class="tag active">Completed</span></td>
        </tr>
      `).join('');

      H(`
        <div class="card" style="max-width:900px;margin:20px auto;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;">
            <div>
              <h2>🏆 LIVE CLASSROOM LEADERBOARD</h2>
              <p class="mu">${esc(data.quiz_title)} — ${esc(data.classroom_name)}</p>
            </div>
            <div>
              <span class="tag ${data.is_active ? 'active' : 'completed'}">
                ${data.is_active ? '● LIVE QUIZ IN PROGRESS' : 'QUIZ COMPLETED'}
              </span>
            </div>
          </div>

          <div class="grid cols-3" style="margin: 20px 0;">
            <div class="card" style="text-align:center;">
              <div class="stat">${data.completed_students} / ${data.total_students}</div>
              <div class="mu">Students Completed</div>
            </div>
            <div class="card" style="text-align:center;">
              <div class="stat">${data.leaderboard.length ? data.leaderboard[0].percentage + '%' : '—'}</div>
              <div class="mu">Top Score</div>
            </div>
            <div class="card" style="text-align:center;">
              <div class="stat">${data.my_rank ? '#' + data.my_rank.rank : '—'}</div>
              <div class="mu">My Rank</div>
            </div>
          </div>

          ${data.leaderboard.length ? `
            <table class="t">
              <thead><tr><th>Rank</th><th>Student Name</th><th>Score</th><th>Time Taken</th><th>Status</th></tr></thead>
              <tbody>${rowsHtml}</tbody>
            </table>
          ` : emptyCard('No students have submitted this quiz yet. Leaderboard updates automatically in real-time!')}
        </div>
      `);
    } catch (e) {
      toast(e.message);
    }
  };

  fetchLeaderboard();
  LEADERBOARD_INTERVAL = setInterval(fetchLeaderboard, 3000);
}

// Student Performance View
async function studentPerformanceView() {
  try {
    const perf = await API.f('/student/performance');

    H(`
      <div class="dashboard-header">
        <h1>My Learning Analytics 📊</h1>
        <p class="mu">Track your scores, strength areas, and improvement over time.</p>
      </div>

      <div class="grid cols-4">
        <div class="card">
          <div class="stat">${perf.average_score}%</div>
          <div class="mu">Average Score</div>
        </div>
        <div class="card">
          <div class="stat">${perf.best_score}%</div>
          <div class="mu">Best Quiz Score</div>
        </div>
        <div class="card">
          <div class="stat">${perf.quizzes_completed}</div>
          <div class="mu">Quizzes Completed</div>
        </div>
        <div class="card">
          <div class="stat">${perf.crosswords_completed}</div>
          <div class="mu">Crosswords Solved</div>
        </div>
      </div>

      <div class="grid cols-2">
        <div class="card">
          <h3>Strong Topics 💪</h3>
          ${perf.strong_topics.map(t => `<span class="chip on">${esc(t)}</span>`).join('')}
        </div>
        <div class="card">
          <h3>Needs Practice 🎯</h3>
          ${perf.needs_practice.map(t => `<span class="chip">${esc(t)}</span>`).join('')}
        </div>
      </div>

      <div class="card">
        <h3>Quiz Attempt History</h3>
        ${perf.history.length ? `
          <table class="t">
            <thead><tr><th>Quiz Title</th><th>Classroom</th><th>Score</th><th>Date</th></tr></thead>
            <tbody>
              ${perf.history.map(h => `
                <tr>
                  <td><b>${esc(h.quiz_title)}</b></td>
                  <td>${esc(h.classroom_name)}</td>
                  <td><b>${h.score_percentage}%</b> (${h.correct}/${h.total})</td>
                  <td>${h.date}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        ` : emptyCard('No completed quiz attempts yet.')}
      </div>
    `);
  } catch (e) {
    toast(e.message);
  }
}

// Teacher Classroom Analytics View
async function teacherAnalyticsView(classId) {
  try {
    const data = await API.f(`/classrooms/${classId}/analytics`);

    H(`
      <div class="card" style="max-width: 900px; margin: 20px auto;">
        <h2>Classroom Performance Analytics 📈</h2>
        
        <div class="grid cols-4" style="margin:20px 0;">
          <div class="card" style="text-align:center;">
            <div class="stat">${data.average_score}%</div>
            <div class="mu">Class Avg Score</div>
          </div>
          <div class="card" style="text-align:center;">
            <div class="stat">${data.highest_score}%</div>
            <div class="mu">Highest Score</div>
          </div>
          <div class="card" style="text-align:center;">
            <div class="stat">${data.participation_rate}%</div>
            <div class="mu">Participation Rate</div>
          </div>
          <div class="card" style="text-align:center;">
            <div class="stat">${data.total_attempts}</div>
            <div class="mu">Total Submissions</div>
          </div>
        </div>

        <h3>Question Accuracy Breakdown</h3>
        <p class="mu">Identifies concept areas where students need clarification.</p>

        ${data.question_accuracy.length ? `
          <div style="margin-top:16px;">
            ${data.question_accuracy.map(q => `
              <div style="margin-bottom:14px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                  <span><b>${esc(q.quiz_title)}:</b> ${esc(q.question)}</span>
                  <b>${q.accuracy_percentage}% Correct</b>
                </div>
                <div style="background:var(--bd);height:12px;border-radius:6px;overflow:hidden;">
                  <div style="width:${q.accuracy_percentage}%;background:var(--p);height:100%;"></div>
                </div>
              </div>
            `).join('')}
          </div>
        ` : emptyCard('No attempts recorded yet to render accuracy stats.')}
      </div>
    `);
  } catch (e) {
    toast(e.message);
  }
}

// Individual Crossword Views
let CW_DOC = null;
let CW_LEVEL = 'medium';

function createCrosswordView() {
  CW_DOC = null;
  H(`
    <h1>Generate AI Crossword</h1>
    <div class="card">
      <h3>1. Upload Material or Enter Topic</h3>
      <div id="drop" class="card" style="border-style:dashed;text-align:center">
        Drop files here or <input type="file" id="fi" multiple accept=".pdf,.pptx,.docx,.xlsx,.xls,.csv,.txt"><br>
        <small class="mu">PDF • PPTX • DOCX • XLSX • CSV • TXT</small>
      </div>

      <label>Topic / Subject
        <input id="tp" placeholder="e.g. Machine Learning, Computer Networks, DBMS">
      </label>

      <button class="btn alt" onclick="startVoiceInput('#tp')">🎙 Speak Topic / Material</button>

      <label style="margin-top:12px;">Or Paste Notes
        <textarea id="tx" rows="4" placeholder="Paste study notes here..."></textarea>
      </label>

      <button class="btn accent lg block" onclick="analyzeCrosswordDoc()">Analyze Content</button>
    </div>
    <div id="cw-step2"></div>
  `);

  const d = $('#drop');
  if (d) {
    d.ondragover = e => e.preventDefault();
    d.ondrop = e => {
      e.preventDefault();
      $('#fi').files = e.dataTransfer.files;
    };
  }
}

async function analyzeCrosswordDoc() {
  const f = new FormData();
  [...$('#fi').files].forEach(x => f.append('files', x));
  f.append('text', $('#tx').value);
  f.append('topic', $('#tp').value);
  $('#cw-step2').innerHTML = emptyCard('Reading document... Extracting concepts...');

  try {
    CW_DOC = await API.f('/documents/analyze', { method: 'POST', body: f });
    
    $('#cw-step2').innerHTML = `
      <div class="card">
        <h3>2. Concept Selection: ${esc(CW_DOC.name)}</h3>
        <p>${CW_DOC.segments} sections · ${CW_DOC.sentences} sentences · ${CW_DOC.concepts.length} concepts found.</p>
        <div id="cc">
          ${CW_DOC.concepts.map(c => `
            <span class="chip on" tabindex="0" data-t="${c.term}" onclick="this.classList.toggle('on')">
              ${c.term} <small>${c.importance}</small>
            </span>
          `).join('')}
        </div>
      </div>

      <div class="card">
        <h3>3. Select Difficulty & Clue Count</h3>
        <div class="grid cols-3">
          <div class="diff ${CW_LEVEL === 'easy' ? 'on' : ''}" onclick="selectDiff('easy', this)">
            <h3>EASY</h3>Direct clues, first letter hints.
          </div>
          <div class="diff ${CW_LEVEL === 'medium' ? 'on' : ''}" onclick="selectDiff('medium', this)">
            <h3>MEDIUM</h3>Paraphrased conceptual clues.
          </div>
          <div class="diff ${CW_LEVEL === 'hard' ? 'on' : ''}" onclick="selectDiff('hard', this)">
            <h3>HARD</h3>Indirect clues, minimal hints.
          </div>
        </div>

        <label style="margin-top:16px;">Number of Clues
          <select id="n"><option>10</option><option selected>15</option><option>20</option></select>
        </label>

        <button class="btn primary lg block" onclick="generateCrosswordPuzzle()">Create Crossword Puzzle</button>
      </div>
    `;
  } catch (e) {
    $('#cw-step2').innerHTML = '';
    toast(e.message);
  }
}

function selectDiff(lvl, el) {
  CW_LEVEL = lvl;
  $$('.diff').forEach(e => e.classList.remove('on'));
  el.classList.add('on');
}

async function generateCrosswordPuzzle() {
  const concepts = [...$$('#cc .on')].map(e => e.dataset.t);
  toast('Building crossword grid...');
  try {
    const p = await API.f('/crosswords/generate', {
      method: 'POST',
      json: {
        doc_id: CW_DOC.doc_id,
        difficulty: CW_LEVEL,
        count: +$('#n').value,
        concepts: concepts
      }
    });
    location.hash = 'play-crossword/' + p.id;
  } catch (e) {
    toast(e.message);
  }
}

// Interactive Crossword Player
let PLAY_PUZZLE = null;
let PLAY_SEL = null;
let PLAY_DIR = 'across';
let PLAY_SECS = 0;
let PLAY_TIMER = null;

async function playCrosswordView(id) {
  PLAY_PUZZLE = await API.f('/crosswords/' + id);
  PLAY_SECS = 0;
  
  const [R, C] = PLAY_PUZZLE.size;
  const cellNums = {};
  PLAY_PUZZLE.clues.forEach(c => {
    cellNums[`${c.row},${c.col}`] = c.n;
  });

  const isCompleted = PLAY_PUZZLE.done;

  H(`
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
      <h1>${esc(PLAY_PUZZLE.title)} <span class="tag active">${PLAY_PUZZLE.difficulty.toUpperCase()}</span></h1>
      <div class="side">
        <b id="cw-timer">Timer: 00:00</b>
        <button class="btn accent" onclick="useCrosswordHint()">Hint (−2 pts)</button>
        <button class="btn primary" onclick="submitCrosswordPuzzle()">Submit Puzzle</button>
        <button class="btn alt" onclick="exportCrosswordPrint(${id})">Export Printable PDF</button>
      </div>
    </div>

    <div class="play">
      <div class="card">
        <table class="xw">
          ${[...Array(R)].map((_, r) => `
            <tr>
              ${[...Array(C)].map((_, c) => {
                const k = `${r},${c}`;
                const hasCell = PLAY_PUZZLE.clues.some(clue => {
                  for (let i = 0; i < clue.len; i++) {
                    const cr = clue.row + (clue.dir === 'down' ? i : 0);
                    const cc = clue.col + (clue.dir === 'across' ? i : 0);
                    if (cr === r && cc === c) return true;
                  }
                  return false;
                });

                if (hasCell) {
                  return `
                    <td class="c" data-k="${k}">
                      <i>${cellNums[k] || ''}</i>
                      <input maxlength="1" data-k="${k}" aria-label="Row ${r+1} col ${c+1}">
                    </td>
                  `;
                }
                return '<td></td>';
              }).join('')}
            </tr>
          `).join('')}
        </table>
      </div>

      <div class="card" style="max-height: 500px; overflow-y: auto;">
        ${['across', 'down'].map(dir => `
          <h3>${dir.toUpperCase()} CLUES</h3>
          <ul style="padding:0;list-style:none;">
            ${PLAY_PUZZLE.clues.filter(c => c.dir === dir).map(c => `
              <li class="cl" id="clue-${c.n}-${dir}" style="margin-bottom:8px;padding:6px;border-radius:6px;cursor:pointer;" onclick="selectClue(${c.n}, '${dir}')">
                <b>${c.n}.</b> ${esc(c.clue)}
                <button class="btn alt" style="padding:2px 8px;font-size:12px;" onclick="event.stopPropagation();speakText('${esc(c.clue)}')">🔊 Listen</button>
              </li>
            `).join('')}
          </ul>
        `).join('')}
      </div>
    </div>
    <div id="cw-results"></div>
  `);

  clearInterval(PLAY_TIMER);
  PLAY_TIMER = setInterval(() => {
    PLAY_SECS++;
    const tDisp = $('#cw-timer');
    if (tDisp) tDisp.textContent = `Timer: ${Math.floor(PLAY_SECS / 60)}:${String(PLAY_SECS % 60).padStart(2, '0')}`;
  }, 1000);

  $$('td.c input').forEach(inp => {
    inp.onfocus = () => { PLAY_SEL = inp.dataset.k; };
    inp.oninput = () => {
      inp.value = inp.value.replace(/[^a-z]/gi, '').toUpperCase();
    };
  });
}

function speakText(txt) {
  if ('speechSynthesis' in window) {
    speechSynthesis.cancel();
    speechSynthesis.speak(new SpeechSynthesisUtterance(txt));
  }
}

async function useCrosswordHint() {
  if (!PLAY_SEL) return toast('Click a cell in the crossword first!');
  const parts = PLAY_SEL.split(',');
  const r = +parts[0], c = +parts[1];

  const matchingClue = PLAY_PUZZLE.clues.find(cl => {
    for (let i = 0; i < cl.len; i++) {
      const cr = cl.row + (cl.dir === 'down' ? i : 0);
      const cc = cl.col + (cl.dir === 'across' ? i : 0);
      if (cr === r && cc === c) return true;
    }
    return false;
  });

  if (!matchingClue) return;

  try {
    const res = await API.f(`/crosswords/${PLAY_PUZZLE.id}/hint`, {
      method: 'POST',
      json: { n: matchingClue.n, dir: matchingClue.dir }
    });
    toast('Hint applied! (−2 points)');
  } catch (e) {
    toast(e.message);
  }
}

async function submitCrosswordPuzzle() {
  const userAnswers = {};
  PLAY_PUZZLE.clues.forEach(c => {
    let val = '';
    for (let i = 0; i < c.len; i++) {
      const cr = c.row + (c.dir === 'down' ? i : 0);
      const cc = c.col + (c.dir === 'across' ? i : 0);
      const inp = document.querySelector(`input[data-k="${cr},${cc}"]`);
      val += (inp && inp.value ? inp.value : ' ');
    }
    userAnswers[`${c.n}-${c.dir}`] = val;
  });

  try {
    const res = await API.f(`/crosswords/${PLAY_PUZZLE.id}/submit`, {
      method: 'POST',
      json: { answers: userAnswers, secs: PLAY_SECS }
    });

    clearInterval(PLAY_TIMER);
    $('#cw-results').innerHTML = `
      <div class="card" style="margin-top:20px;">
        <h2>Score: ${res.score}% 🎉</h2>
        <p>Correct: ${res.correct}/${res.total} · Time: ${Math.floor(res.secs/60)}m ${res.secs%60}s</p>
        <button class="btn alt" onclick="exportCrosswordPrint(${PLAY_PUZZLE.id})">Download PDF Export</button>
      </div>
    `;
    toast('Crossword submitted!');
  } catch (e) {
    toast(e.message);
  }
}

async function exportCrosswordPrint(id) {
  const r = await fetch(API_BASE + `/api/crosswords/${id}/export`, {
    headers: { Authorization: 'Bearer ' + localStorage.ct }
  });
  const blob = new Blob([await r.text()], { type: 'text/html' });
  open(URL.createObjectURL(blob));
}

// History View
async function historyView() {
  const crosswords = await API.f('/crosswords');
  H(`
    <h2>Crossword History</h2>
    ${crosswords.length ? `
      <table class="t">
        <thead><tr><th>Topic</th><th>Difficulty</th><th>Score</th><th>Date</th><th>Action</th></tr></thead>
        <tbody>
          ${crosswords.map(x => `
            <tr>
              <td><b>${esc(x.title)}</b></td>
              <td>${x.difficulty.toUpperCase()}</td>
              <td>${x.score !== null ? x.score + '%' : 'In Progress'}</td>
              <td>${x.created.slice(0, 10)}</td>
              <td>
                <a class="btn primary" href="#play-crossword/${x.id}">Play</a>
                <button class="btn alt" onclick="exportCrosswordPrint(${x.id})">Export PDF</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    ` : emptyCard('No history yet.')}
  `);
}
