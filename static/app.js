'use strict';

const API = '/api';
const CACHE_KEY = 'reservation-app-state-v2';

const state = {
  cars: [],
  members: [],
  reservations: [],
  users: [],
  currentUser: null,
  activeTab: 'home',
  calendarCursor: startOfMonth(new Date()),
  selectedDate: startOfDay(new Date()),
};

const TAB_TITLES = {
  home: 'ホーム',
  reserve: '予約する',
  list: '予約一覧',
  settings: '設定',
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const els = {
  boot: $('#boot'),
  loginScreen: $('#loginScreen'),
  loginForm: $('#loginForm'),
  loginSubmit: $('#loginSubmit'),
  loginError: $('#loginError'),
  username: $('#username'),
  password: $('#password'),
  app: $('#app'),
  todayLabel: $('#todayLabel'),
  pageTitle: $('#pageTitle'),
  currentUserBadge: $('#currentUserBadge'),
  carStatusList: $('#carStatusList'),
  homeUpcoming: $('#homeUpcoming'),
  reserveCar: $('#reserveCar'),
  reserveMember: $('#reserveMember'),
  reservationForm: $('#reservationForm'),
  startTime: $('#startTime'),
  endTime: $('#endTime'),
  note: $('#note'),
  reserveSubmit: $('#reserveSubmit'),
  calendarTitle: $('#calendarTitle'),
  calendarPrev: $('#calendarPrev'),
  calendarToday: $('#calendarToday'),
  calendarNext: $('#calendarNext'),
  calendarGrid: $('#calendarGrid'),
  calendarDayList: $('#calendarDayList'),
  selectedDayTitle: $('#selectedDayTitle'),
  pastList: $('#pastList'),
  carSettingsList: $('#carSettingsList'),
  memberSettingsList: $('#memberSettingsList'),
  userSettingsList: $('#userSettingsList'),
  carForm: $('#carForm'),
  carName: $('#carName'),
  carPlate: $('#carPlate'),
  carColor: $('#carColor'),
  memberForm: $('#memberForm'),
  memberName: $('#memberName'),
  userForm: $('#userForm'),
  userName: $('#userName'),
  userPassword: $('#userPassword'),
  userRole: $('#userRole'),
  userMember: $('#userMember'),
  toast: $('#toast'),
  carDialog: $('#carDialog'),
  memberDialog: $('#memberDialog'),
  userDialog: $('#userDialog'),
  carEditForm: $('#carEditForm'),
  memberEditForm: $('#memberEditForm'),
  userEditForm: $('#userEditForm'),
  editCarId: $('#editCarId'),
  editCarName: $('#editCarName'),
  editCarPlate: $('#editCarPlate'),
  editCarColor: $('#editCarColor'),
  editMemberId: $('#editMemberId'),
  editMemberName: $('#editMemberName'),
  editUserId: $('#editUserId'),
  editUserName: $('#editUserName'),
  editUserPassword: $('#editUserPassword'),
  editUserRole: $('#editUserRole'),
  editUserMember: $('#editUserMember'),
};

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function endOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + 1);
}

function dateKey(date) {
  const pad = (number) => String(number).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function parseDateKey(value) {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function isAdmin() {
  return state.currentUser?.role === 'admin';
}

function saveCachedState() {
  try {
    localStorage.setItem(
      CACHE_KEY,
      JSON.stringify({
        cars: state.cars,
        members: state.members,
        reservations: state.reservations,
        currentUser: state.currentUser,
        savedAt: Date.now(),
      })
    );
  } catch (_) {
    // ストレージが使えない環境ではキャッシュしない
  }
}

function readCachedState() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (
      !Array.isArray(data.cars) ||
      !Array.isArray(data.members) ||
      !Array.isArray(data.reservations)
    ) {
      return null;
    }
    return data;
  } catch (_) {
    return null;
  }
}

function clearCachedState() {
  try {
    localStorage.removeItem(CACHE_KEY);
  } catch (_) {
    // 何もしない
  }
}

function applyState(data) {
  state.cars = data.cars;
  state.members = data.members;
  state.reservations = data.reservations;
  if (data.currentUser) {
    state.currentUser = data.currentUser;
  }
  renderAll();
}

function renderAll() {
  renderSelects();
  renderHome();
  renderReservationLists();
  renderSettings();
  applyRoleUI();
}

const HTML_ESCAPES = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => HTML_ESCAPES[char]);
}

const dateFormatter = new Intl.DateTimeFormat('ja-JP', {
  month: 'numeric',
  day: 'numeric',
  weekday: 'short',
});

const timeFormatter = new Intl.DateTimeFormat('ja-JP', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

const todayFormatter = new Intl.DateTimeFormat('ja-JP', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  weekday: 'long',
});

const monthFormatter = new Intl.DateTimeFormat('ja-JP', {
  year: 'numeric',
  month: 'long',
});

const selectedDayFormatter = new Intl.DateTimeFormat('ja-JP', {
  month: 'long',
  day: 'numeric',
  weekday: 'long',
});

function formatDateTime(value) {
  const date = new Date(value);
  return `${dateFormatter.format(date)} ${timeFormatter.format(date)}`;
}

function formatRange(start, end) {
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (startDate.toDateString() === endDate.toDateString()) {
    return `${formatDateTime(start)} 〜 ${timeFormatter.format(endDate)}`;
  }
  return `${formatDateTime(start)} 〜 ${formatDateTime(end)}`;
}

function toLocalInput(date) {
  const pad = (number) => String(number).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

let toastTimer = null;
let toastHideTimer = null;

function toast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.classList.toggle('is-error', isError);
  els.toast.hidden = false;
  requestAnimationFrame(() => els.toast.classList.add('is-visible'));

  clearTimeout(toastTimer);
  clearTimeout(toastHideTimer);
  toastTimer = setTimeout(() => {
    els.toast.classList.remove('is-visible');
    toastHideTimer = setTimeout(() => {
      els.toast.hidden = true;
    }, 220);
  }, 3200);
}

async function apiFetch(path, options = {}) {
  const config = {
    ...options,
    headers: { ...(options.headers || {}) },
  };

  if (config.body !== undefined && config.body !== null) {
    config.headers['Content-Type'] = 'application/json';
  }

  let response;
  try {
    response = await fetch(`${API}${path}`, config);
  } catch (_) {
    throw new Error('サーバーに接続できませんでした');
  }

  if (response.status === 401) {
    showLogin('ログインの有効期限が切れました。もう一度ログインしてください。');
    throw new Error('unauthorized');
  }

  if (!response.ok) {
    let message = `エラーが発生しました（${response.status}）`;
    try {
      const data = await response.json();
      if (typeof data.detail === 'string') {
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        message = data.detail.map((item) => item.msg).join(' / ');
      }
    } catch (_) {
      // JSON以外のレスポンスは既定メッセージを使う
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

function applyRoleUI() {
  const admin = isAdmin();

  $$('[data-tab="settings"]', els.app).forEach((button) => {
    button.hidden = !admin;
  });

  if (state.currentUser) {
    els.currentUserBadge.hidden = false;
    els.currentUserBadge.textContent = `${state.currentUser.username}（${
      admin ? '管理者' : '利用者'
    }）`;
  } else {
    els.currentUserBadge.hidden = true;
  }

  if (!admin && state.activeTab === 'settings') {
    switchTab('home');
  }
}

function showLogin(message = '') {
  if (els.carDialog?.open) els.carDialog.close();
  if (els.memberDialog?.open) els.memberDialog.close();
  if (els.userDialog?.open) els.userDialog.close();
  state.currentUser = null;
  state.users = [];
  els.app.hidden = true;
  els.loginScreen.hidden = false;
  els.boot.hidden = true;
  els.loginError.hidden = !message;
  els.loginError.textContent = message;
  document.title = 'ログイン | 予約アプリ';
  setTimeout(() => {
    if (!els.username.value) {
      els.username.focus();
    } else {
      els.password.focus();
    }
  }, 50);
}

function showApp() {
  els.loginScreen.hidden = true;
  els.app.hidden = false;
  els.boot.hidden = true;
  els.password.value = '';
  els.loginError.hidden = true;
  document.title = '予約アプリ';
}

function showLoginError(message) {
  els.loginError.textContent = message;
  els.loginError.hidden = false;
}

function setLoginBusy(isBusy) {
  els.loginSubmit.disabled = isBusy;
  els.loginSubmit.textContent = isBusy ? 'ログイン中...' : 'ログイン';
}

async function login(username, password) {
  const response = await fetch(`${API}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      typeof data.detail === 'string' ? data.detail : 'ログインできませんでした'
    );
  }
  return data;
}

async function logout() {
  try {
    await fetch(`${API}/auth/logout`, { method: 'POST' });
  } catch (_) {
    // 通信できなくても画面上はログアウトする
  }

  clearCachedState();
  state.cars = [];
  state.members = [];
  state.reservations = [];
  state.users = [];
  state.currentUser = null;
  switchTab('home');
  showLogin();
  toast('ログアウトしました');
}

async function loadAll() {
  try {
    const requests = [
      apiFetch('/cars/'),
      apiFetch('/members/'),
      apiFetch('/reservations/'),
    ];
    if (isAdmin()) {
      requests.push(apiFetch('/users/'));
    }

    const [cars, members, reservations, users = []] = await Promise.all(requests);

    state.cars = cars;
    state.members = members;
    state.reservations = reservations;
    state.users = users;

    renderAll();
    saveCachedState();
  } catch (error) {
    if (error.message !== 'unauthorized') {
      const cached = readCachedState();
      if (cached) {
        applyState(cached);
        toast('通信に失敗したため、保存済みのデータを表示しています。', true);
      } else {
        toast(error.message, true);
      }
    }
  }
}

function memberOptionMarkup(members, selectedId) {
  const options = ['<option value="">なし</option>'];
  members.forEach((member) => {
    const selected = String(member.id) === String(selectedId) ? ' selected' : '';
    options.push(
      `<option value="${member.id}"${selected}>${esc(member.name)}</option>`
    );
  });
  return options.join('');
}

function renderSelects() {
  const selectedCar = els.reserveCar.value;
  const selectedMember = els.reserveMember.value;
  const admin = isAdmin();
  const ownMember = state.members.find(
    (member) => member.id === state.currentUser?.member_id
  );

  els.reserveCar.innerHTML = state.cars.length
    ? state.cars
        .map(
          (car) =>
            `<option value="${car.id}">${esc(car.name)}（${esc(car.color)}）</option>`
        )
        .join('')
    : '<option value="">車が登録されていません</option>';

  if (admin) {
    els.reserveMember.disabled = false;
    els.reserveMember.innerHTML = state.members.length
      ? state.members
          .map(
            (member) => `<option value="${member.id}">${esc(member.name)}</option>`
          )
          .join('')
      : '<option value="">住人が登録されていません</option>';
  } else if (ownMember) {
    els.reserveMember.disabled = true;
    els.reserveMember.innerHTML = `<option value="${ownMember.id}">${esc(
      ownMember.name
    )}</option>`;
  } else {
    els.reserveMember.disabled = true;
    els.reserveMember.innerHTML =
      '<option value="">住人が紐付いていません</option>';
  }

  if (state.cars.some((car) => String(car.id) === selectedCar)) {
    els.reserveCar.value = selectedCar;
  }
  if (
    admin &&
    state.members.some((member) => String(member.id) === selectedMember)
  ) {
    els.reserveMember.value = selectedMember;
  }

  const noCars = state.cars.length === 0;
  const noMembers = admin ? state.members.length === 0 : !ownMember;
  els.reserveSubmit.disabled = noCars || noMembers;
  els.reserveSubmit.textContent = noCars
    ? admin
      ? '先に車を登録してください'
      : '管理者に車の登録を依頼してください'
    : noMembers
      ? admin
        ? '先に住人を登録してください'
        : '管理者に住人の紐付けを依頼してください'
      : '予約する';
}

function emptyState(message) {
  return `<div class="empty">${esc(message)}</div>`;
}

function renderHome() {
  const now = Date.now();

  if (!state.cars.length) {
    els.carStatusList.innerHTML = emptyState(
      '車がまだ登録されていません。設定から追加してください。'
    );
  } else {
    els.carStatusList.innerHTML = state.cars
      .map((car) => {
        const reservations = state.reservations.filter(
          (reservation) => reservation.car_id === car.id
        );
        const current = reservations.find(
          (reservation) =>
            new Date(reservation.start_time).getTime() <= now &&
            new Date(reservation.end_time).getTime() > now
        );
        const next = reservations
          .filter(
            (reservation) => new Date(reservation.start_time).getTime() > now
          )
          .sort(
            (a, b) =>
              new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
          )[0];

        let detail;
        if (current) {
          detail = `<strong>${esc(current.member.name)}</strong> が利用中<br>${esc(
            formatRange(current.start_time, current.end_time)
          )}`;
        } else if (next) {
          detail = `次の予約：${esc(formatDateTime(next.start_time))}<br>利用者：<strong>${esc(
            next.member.name
          )}</strong>`;
        } else {
          detail = '予約はありません';
        }

        return `
          <article class="car-card ${current ? 'is-busy' : ''}">
            <div class="car-top">
              <div>
                <div class="car-name">${esc(car.name)}</div>
                <div class="car-meta">${esc(car.color)} / ${esc(car.plate)}</div>
              </div>
              <span class="badge ${current ? 'badge--busy' : 'badge--free'}">${
                current ? '使用中' : '空き'
              }</span>
            </div>
            <div class="car-detail">${detail}</div>
          </article>
        `;
      })
      .join('');
  }

  const upcoming = state.reservations
    .filter((reservation) => new Date(reservation.end_time).getTime() >= now)
    .sort(
      (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    )
    .slice(0, 3);

  els.homeUpcoming.innerHTML = upcoming.length
    ? upcoming.map((reservation) => reservationCard(reservation, false)).join('')
    : emptyState('今後の予約はありません');
}

function canCancelReservation(reservation) {
  if (!state.currentUser) return false;
  if (isAdmin()) return true;
  return reservation.member_id === state.currentUser.member_id;
}

function reservationCard(reservation, showActions) {
  const isUpcoming = new Date(reservation.end_time).getTime() > Date.now();
  const cancelButton =
    showActions && isUpcoming && canCancelReservation(reservation)
      ? `<button class="btn btn-danger btn-small" type="button" data-action="cancel-reservation" data-id="${reservation.id}">キャンセル</button>`
      : '';

  return `
    <article class="reservation-card">
      <div class="reservation-main">
        <div class="reservation-title">
          ${esc(reservation.car.name)}
          <span class="chip">${esc(reservation.member.name)}</span>
        </div>
        <div class="reservation-time">${esc(
          formatRange(reservation.start_time, reservation.end_time)
        )}</div>
        ${
          reservation.note
            ? `<div class="reservation-note">${esc(reservation.note)}</div>`
            : ''
        }
      </div>
      ${cancelButton ? `<div class="reservation-actions">${cancelButton}</div>` : ''}
    </article>
  `;
}

function reservationsForDay(date) {
  const dayStart = startOfDay(date).getTime();
  const dayEnd = endOfDay(date).getTime();
  return state.reservations
    .filter((reservation) => {
      const start = new Date(reservation.start_time).getTime();
      const end = new Date(reservation.end_time).getTime();
      return start < dayEnd && end > dayStart;
    })
    .sort(
      (a, b) =>
        new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    );
}

function renderCalendar() {
  els.calendarTitle.textContent = monthFormatter.format(state.calendarCursor);

  const monthStart = startOfMonth(state.calendarCursor);
  const gridStart = new Date(
    monthStart.getFullYear(),
    monthStart.getMonth(),
    1 - monthStart.getDay()
  );
  const today = startOfDay(new Date());
  const selectedKey = dateKey(state.selectedDate);

  const cells = [];
  for (let index = 0; index < 42; index += 1) {
    const date = new Date(
      gridStart.getFullYear(),
      gridStart.getMonth(),
      gridStart.getDate() + index
    );
    const key = dateKey(date);
    const dayReservations = reservationsForDay(date);
    const outside = date.getMonth() !== state.calendarCursor.getMonth();
    const classes = ['calendar-day'];

    if (outside) classes.push('is-outside');
    if (key === selectedKey) classes.push('is-selected');
    if (key === dateKey(today)) classes.push('is-today');
    if (dayReservations.length) classes.push('has-reservations');

    const chips = dayReservations.slice(0, 3).map((reservation) => {
      const start = new Date(reservation.start_time);
      const dayStart = startOfDay(date);
      const timeLabel =
        start < dayStart ? '継続' : timeFormatter.format(start);
      const own = reservation.member_id === state.currentUser?.member_id;
      return `<span class="calendar-chip ${own ? 'is-own' : ''}">${esc(
        timeLabel
      )} ${esc(reservation.car.name)}</span>`;
    });
    if (dayReservations.length > 3) {
      chips.push(
        `<span class="calendar-more">+${dayReservations.length - 3}件</span>`
      );
    }

    cells.push(`
      <button class="${classes.join(' ')}" type="button" data-calendar-date="${key}" aria-pressed="${
        key === selectedKey
      }">
        <span class="calendar-day-number">${date.getDate()}</span>
        <span class="calendar-chips">${chips.join('')}</span>
      </button>
    `);
  }

  els.calendarGrid.innerHTML = cells.join('');
}

function renderCalendarDay() {
  const dayReservations = reservationsForDay(state.selectedDate);
  els.selectedDayTitle.textContent = `${selectedDayFormatter.format(
    state.selectedDate
  )}の予約`;
  els.calendarDayList.innerHTML = dayReservations.length
    ? dayReservations
        .map((reservation) => reservationCard(reservation, true))
        .join('')
    : emptyState('この日の予約はありません');
}

function renderPastReservations() {
  const now = Date.now();
  const past = state.reservations
    .filter((reservation) => new Date(reservation.end_time).getTime() < now)
    .sort(
      (a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()
    );

  els.pastList.innerHTML = past.length
    ? past.map((reservation) => reservationCard(reservation, false)).join('')
    : emptyState('過去の予約はありません');
}

function renderReservationLists() {
  renderCalendar();
  renderCalendarDay();
  renderPastReservations();
}

function renderSettings() {
  const editIcon =
    '<svg class="icon" aria-hidden="true"><use href="#icon-edit"></use></svg>';
  const trashIcon =
    '<svg class="icon" aria-hidden="true"><use href="#icon-trash"></use></svg>';

  els.carSettingsList.innerHTML = state.cars.length
    ? state.cars
        .map(
          (car) => `
            <div class="setting-row">
              <div class="setting-info">
                <strong>${esc(car.name)}</strong>
                <span>${esc(car.color)} / ${esc(car.plate)}</span>
              </div>
              <div class="setting-actions">
                <button class="icon-btn" type="button" data-action="edit-car" data-id="${
                  car.id
                }" aria-label="${esc(car.name)}を編集">${editIcon}</button>
                <button class="icon-btn icon-btn--danger" type="button" data-action="delete-car" data-id="${
                  car.id
                }" aria-label="${esc(car.name)}を削除">${trashIcon}</button>
              </div>
            </div>
          `
        )
        .join('')
    : emptyState('車が登録されていません');

  els.memberSettingsList.innerHTML = state.members.length
    ? state.members
        .map(
          (member) => `
            <div class="setting-row">
              <div class="setting-info">
                <strong>${esc(member.name)}</strong>
              </div>
              <div class="setting-actions">
                <button class="icon-btn" type="button" data-action="edit-member" data-id="${
                  member.id
                }" aria-label="${esc(member.name)}を編集">${editIcon}</button>
                <button class="icon-btn icon-btn--danger" type="button" data-action="delete-member" data-id="${
                  member.id
                }" aria-label="${esc(member.name)}を削除">${trashIcon}</button>
              </div>
            </div>
          `
        )
        .join('')
    : emptyState('住人が登録されていません');

  const currentUserMember = els.userMember.value;
  els.userMember.innerHTML = memberOptionMarkup(state.members, currentUserMember);
  const currentEditMember = els.editUserMember.value;
  els.editUserMember.innerHTML = memberOptionMarkup(
    state.members,
    currentEditMember
  );

  if (!isAdmin()) {
    els.userSettingsList.innerHTML = '';
    return;
  }

  els.userSettingsList.innerHTML = state.users.length
    ? state.users
        .map((user) => {
          const roleLabel = user.role === 'admin' ? '管理者' : '利用者';
          const memberLabel = user.member_name
            ? esc(user.member_name)
            : '住人の紐付けなし';
          return `
            <div class="setting-row">
              <div class="setting-info">
                <strong>${esc(user.username)}</strong>
                <span><span class="role-badge role-badge--${user.role}">${roleLabel}</span> ${memberLabel}</span>
              </div>
              <div class="setting-actions">
                <button class="icon-btn" type="button" data-action="edit-user" data-id="${
                  user.id
                }" aria-label="${esc(user.username)}を編集">${editIcon}</button>
                <button class="icon-btn icon-btn--danger" type="button" data-action="delete-user" data-id="${
                  user.id
                }" aria-label="${esc(user.username)}を削除">${trashIcon}</button>
              </div>
            </div>
          `;
        })
        .join('')
    : emptyState('ユーザーが登録されていません');
}

function switchTab(tab) {
  if (!TAB_TITLES[tab]) return;
  if (tab === 'settings' && !isAdmin()) {
    toast('設定は管理者のみ利用できます', true);
    return;
  }

  state.activeTab = tab;
  $$('.tab-panel').forEach((panel) => {
    panel.hidden = panel.id !== `panel-${tab}`;
  });
  $$('[data-tab]').forEach((button) => {
    const isActive = button.dataset.tab === tab;
    button.classList.toggle('is-active', isActive);
    if (isActive) {
      button.setAttribute('aria-current', 'page');
    } else {
      button.removeAttribute('aria-current');
    }
  });

  if (tab === 'list') {
    renderCalendar();
    renderCalendarDay();
  }

  els.pageTitle.textContent = TAB_TITLES[tab];
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function setDefaultTimes() {
  const start = new Date();
  start.setSeconds(0, 0);
  start.setMinutes(start.getMinutes() < 30 ? 30 : 60);
  const end = new Date(start.getTime() + 60 * 60 * 1000);

  els.startTime.value = toLocalInput(start);
  els.endTime.value = toLocalInput(end);
}

function openCarDialog(carId) {
  const car = state.cars.find((item) => item.id === carId);
  if (!car) return;

  els.editCarId.value = car.id;
  els.editCarName.value = car.name;
  els.editCarPlate.value = car.plate;
  els.editCarColor.value = car.color;
  els.carDialog.showModal();
}

function openMemberDialog(memberId) {
  const member = state.members.find((item) => item.id === memberId);
  if (!member) return;

  els.editMemberId.value = member.id;
  els.editMemberName.value = member.name;
  els.memberDialog.showModal();
}

function openUserDialog(userId) {
  const user = state.users.find((item) => item.id === userId);
  if (!user) return;

  els.editUserId.value = user.id;
  els.editUserName.value = user.username;
  els.editUserPassword.value = '';
  els.editUserRole.value = user.role;
  els.editUserMember.innerHTML = memberOptionMarkup(
    state.members,
    user.member_id ?? ''
  );
  els.userDialog.showModal();
}

async function deleteCar(carId) {
  if (!window.confirm('この車を削除しますか？')) return;
  try {
    await apiFetch(`/cars/${carId}`, { method: 'DELETE' });
    toast('車を削除しました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function deleteMember(memberId) {
  if (!window.confirm('この住人を削除しますか？')) return;
  try {
    await apiFetch(`/members/${memberId}`, { method: 'DELETE' });
    toast('住人を削除しました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function deleteUser(userId) {
  if (!window.confirm('このユーザーを削除しますか？')) return;
  try {
    await apiFetch(`/users/${userId}`, { method: 'DELETE' });
    toast('ユーザーを削除しました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function cancelReservation(reservationId) {
  if (!window.confirm('この予約をキャンセルしますか？')) return;
  try {
    await apiFetch(`/reservations/${reservationId}`, { method: 'DELETE' });
    toast('予約をキャンセルしました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function handleAction(action, id) {
  switch (action) {
    case 'edit-car':
      openCarDialog(id);
      break;
    case 'delete-car':
      await deleteCar(id);
      break;
    case 'edit-member':
      openMemberDialog(id);
      break;
    case 'delete-member':
      await deleteMember(id);
      break;
    case 'edit-user':
      openUserDialog(id);
      break;
    case 'delete-user':
      await deleteUser(id);
      break;
    case 'cancel-reservation':
      await cancelReservation(id);
      break;
    default:
      break;
  }
}

function selectCalendarDate(date) {
  state.selectedDate = startOfDay(date);
  state.calendarCursor = startOfMonth(date);
  renderCalendar();
  renderCalendarDay();
}

function moveCalendar(months) {
  state.calendarCursor = new Date(
    state.calendarCursor.getFullYear(),
    state.calendarCursor.getMonth() + months,
    1
  );
  if (
    state.selectedDate.getFullYear() !== state.calendarCursor.getFullYear() ||
    state.selectedDate.getMonth() !== state.calendarCursor.getMonth()
  ) {
    state.selectedDate = startOfMonth(state.calendarCursor);
  }
  renderCalendar();
  renderCalendarDay();
}

function bindEvents() {
  els.loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const username = els.username.value.trim();
    const password = els.password.value;
    if (!username) {
      showLoginError('ユーザー名を入力してください');
      els.username.focus();
      return;
    }
    if (!password) {
      showLoginError('パスワードを入力してください');
      els.password.focus();
      return;
    }

    setLoginBusy(true);
    els.loginError.hidden = true;
    try {
      const data = await login(username, password);
      state.currentUser = data.user;
      showApp();
      applyRoleUI();
      setDefaultTimes();
      await loadAll();
    } catch (error) {
      showLoginError(
        error instanceof TypeError ? 'サーバーに接続できませんでした' : error.message
      );
      els.password.select();
    } finally {
      setLoginBusy(false);
    }
  });

  $('#logoutBtn').addEventListener('click', logout);
  $('#logoutBtnMobile').addEventListener('click', logout);

  els.calendarPrev.addEventListener('click', () => moveCalendar(-1));
  els.calendarNext.addEventListener('click', () => moveCalendar(1));
  els.calendarToday.addEventListener('click', () => selectCalendarDate(new Date()));

  els.calendarGrid.addEventListener('click', (event) => {
    const dayButton = event.target.closest('[data-calendar-date]');
    if (!dayButton) return;
    selectCalendarDate(parseDateKey(dayButton.dataset.calendarDate));
  });

  els.reservationForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (!els.reserveCar.value || !els.reserveMember.value) {
      toast('車と住人を登録してください', true);
      return;
    }
    if (!els.startTime.value || !els.endTime.value) {
      toast('日時を入力してください', true);
      return;
    }
    if (new Date(els.endTime.value) <= new Date(els.startTime.value)) {
      toast('終了日時は開始日時より後にしてください', true);
      return;
    }

    const start = new Date(els.startTime.value);
    const payload = {
      car_id: Number(els.reserveCar.value),
      member_id: Number(els.reserveMember.value),
      start_time: els.startTime.value,
      end_time: els.endTime.value,
      note: els.note.value.trim(),
    };

    const submitButton = els.reservationForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    try {
      await apiFetch('/reservations/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      els.note.value = '';
      setDefaultTimes();
      state.calendarCursor = startOfMonth(start);
      state.selectedDate = startOfDay(start);
      toast('予約しました');
      await loadAll();
      switchTab('list');
    } catch (error) {
      if (error.message !== 'unauthorized') toast(error.message, true);
    } finally {
      submitButton.disabled = false;
      renderSelects();
    }
  });

  els.startTime.addEventListener('change', () => {
    if (!els.startTime.value) return;
    const start = new Date(els.startTime.value);
    const end = els.endTime.value ? new Date(els.endTime.value) : null;
    if (!end || end <= start) {
      els.endTime.value = toLocalInput(
        new Date(start.getTime() + 60 * 60 * 1000)
      );
    }
  });

  els.carForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      await apiFetch('/cars/', {
        method: 'POST',
        body: JSON.stringify({
          name: els.carName.value.trim(),
          plate: els.carPlate.value.trim(),
          color: els.carColor.value.trim(),
        }),
      });
      els.carForm.reset();
      toast('車を追加しました');
      await loadAll();
    } catch (error) {
      if (error.message !== 'unauthorized') toast(error.message, true);
    }
  });

  els.memberForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      await apiFetch('/members/', {
        method: 'POST',
        body: JSON.stringify({ name: els.memberName.value.trim() }),
      });
      els.memberForm.reset();
      toast('住人を追加しました');
      await loadAll();
    } catch (error) {
      if (error.message !== 'unauthorized') toast(error.message, true);
    }
  });

  els.userForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (els.userRole.value === 'user' && !els.userMember.value) {
      toast('利用者には住人を紐付けてください', true);
      return;
    }
    try {
      await apiFetch('/users/', {
        method: 'POST',
        body: JSON.stringify({
          username: els.userName.value.trim(),
          password: els.userPassword.value,
          role: els.userRole.value,
          member_id: els.userMember.value
            ? Number(els.userMember.value)
            : null,
        }),
      });
      els.userForm.reset();
      toast('ユーザーを追加しました');
      await loadAll();
    } catch (error) {
      if (error.message !== 'unauthorized') toast(error.message, true);
    }
  });

  els.carEditForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const carId = Number(els.editCarId.value);
    try {
      await apiFetch(`/cars/${carId}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: els.editCarName.value.trim(),
          plate: els.editCarPlate.value.trim(),
          color: els.editCarColor.value.trim(),
        }),
      });
      els.carDialog.close();
      toast('車を更新しました');
      await loadAll();
    } catch (error) {
      if (error.message !== 'unauthorized') toast(error.message, true);
    }
  });

  els.memberEditForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const memberId = Number(els.editMemberId.value);
    try {
      await apiFetch(`/members/${memberId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: els.editMemberName.value.trim() }),
      });
      els.memberDialog.close();
      toast('住人を更新しました');
      await loadAll();
    } catch (error) {
      if (error.message !== 'unauthorized') toast(error.message, true);
    }
  });

  els.userEditForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (els.editUserRole.value === 'user' && !els.editUserMember.value) {
      toast('利用者には住人を紐付けてください', true);
      return;
    }
    const userId = Number(els.editUserId.value);
    const payload = {
      username: els.editUserName.value.trim(),
      role: els.editUserRole.value,
      member_id: els.editUserMember.value
        ? Number(els.editUserMember.value)
        : null,
    };
    if (els.editUserPassword.value) {
      payload.password = els.editUserPassword.value;
    }

    try {
      await apiFetch(`/users/${userId}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      els.userDialog.close();
      toast('ユーザーを更新しました');
      await loadAll();
    } catch (error) {
      if (error.message !== 'unauthorized') toast(error.message, true);
    }
  });

  document.addEventListener('click', (event) => {
    const tabButton = event.target.closest('[data-tab]');
    if (tabButton) {
      switchTab(tabButton.dataset.tab);
      return;
    }

    const goTabButton = event.target.closest('[data-go-tab]');
    if (goTabButton) {
      switchTab(goTabButton.dataset.goTab);
      return;
    }

    const actionButton = event.target.closest('[data-action]');
    if (actionButton) {
      void handleAction(actionButton.dataset.action, Number(actionButton.dataset.id));
      return;
    }

    const closeButton = event.target.closest('[data-close-dialog]');
    if (closeButton) {
      document.getElementById(closeButton.dataset.closeDialog)?.close();
    }
  });

  [els.carDialog, els.memberDialog, els.userDialog].forEach((dialog) => {
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) dialog.close();
    });
  });

  window.addEventListener('offline', () => {
    toast('オフラインです。予約の保存はできません。', true);
  });
}

function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // 登録に失敗してもWebアプリとしては動作する
    });
  });
}

async function init() {
  bindEvents();
  els.todayLabel.textContent = todayFormatter.format(new Date());
  registerServiceWorker();

  try {
    const response = await fetch(`${API}/auth/me`);
    if (response.ok) {
      const data = await response.json();
      state.currentUser = data.user;
      showApp();
      applyRoleUI();
      setDefaultTimes();
      await loadAll();
    } else {
      showLogin();
    }
  } catch (_) {
    const cached = readCachedState();
    if (cached) {
      showApp();
      applyState(cached);
      toast('オフラインのため、保存済みのデータを表示しています。', true);
    } else {
      showLogin('サーバーに接続できませんでした。時間をおいて再度お試しください。');
    }
  } finally {
    els.boot.hidden = true;
  }
}

init();
