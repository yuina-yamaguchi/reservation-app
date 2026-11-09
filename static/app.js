'use strict';

const API = '/api';
const CACHE_KEY = 'reservation-app-state-v5';
const CARPOOL_SEEN_KEY_PREFIX = 'reservation-app-carpool-seen-v1:';
const CARPOOL_POLL_MS = 60000;
let carpoolPollTimer = null;
let carpoolRefreshPromise = null;

const state = {
  cars: [],
  members: [],
  reservations: [],
  users: [],
  plans: [],
  profile: null,
  tickets: [],
  carpools: [],
  myApplications: [],
  keyDevices: [],
  digitalKeys: [],
  masterKeys: [],
  currentUser: null,
  activeTab: 'home',
  calendarCursor: startOfMonth(new Date()),
  selectedDate: startOfDay(new Date()),
  reservationOptions: null,
  selectedPaymentType: 'time',
  billing: null,
  billingUserId: '',
  optionRequestId: 0,
};

const TAB_TITLES = {
  home: 'ホーム',
  reserve: '予約する',
  list: '予約一覧',
  carpool: '相乗り',
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
  notePublic: $('#notePublic'),
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
  carSeatCapacity: $('#carSeatCapacity'),
  editCarSeatCapacity: $('#editCarSeatCapacity'),
  editUserPlan: $('#editUserPlan'),
  editUserGender: $('#editUserGender'),
  editUserRecipient: $('#editUserRecipient'),
  planCard: $('#planCard'),
  billingCard: $('#billingCard'),
  reservationOptions: $('#reservationOptions'),
  reservationOptionsHint: $('#reservationOptionsHint'),
  refreshOptionsBtn: $('#refreshOptionsBtn'),
  carpoolForm: $('#carpoolForm'),
  carpoolReservation: $('#carpoolReservation'),
  carpoolArea: $('#carpoolArea'),
  carpoolGender: $('#carpoolGender'),
  carpoolSeats: $('#carpoolSeats'),
  carpoolGuestSeats: $('#carpoolGuestSeats'),
  carpoolNote: $('#carpoolNote'),
  carpoolNotePublic: $('#carpoolNotePublic'),
  carpoolList: $('#carpoolList'),
  carpoolDialog: $('#carpoolDialog'),
  openCarpoolDialogBtn: $('#openCarpoolDialog'),
  reservationDayModal: $('#reservationDayModal'),
  modalDateTitle: $('#modalDateTitle'),
  modalReservations: $('#modalReservations'),
  keyDeviceList: $('#keyDeviceList'),
  keyDeviceForm: $('#keyDeviceForm'),
  keyDeviceCar: $('#keyDeviceCar'),
  keyDeviceId: $('#keyDeviceId'),
  keyDeviceName: $('#keyDeviceName'),
  masterKeyCar: $('#masterKeyCar'),
  masterPassword: $('#masterPassword'),
  masterReason: $('#masterReason'),
  masterConfirmInUse: $('#masterConfirmInUse'),
  masterKeyBtn: $('#masterKeyBtn'),
  remoteUnlockBtn: $('#remoteUnlockBtn'),
  masterKeyResult: $('#masterKeyResult'),
  masterKeyList: $('#masterKeyList'),
  keyAuditList: $('#keyAuditList'),
  keyAuditRefresh: $('#keyAuditRefresh'),
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
        users: state.users,
        plans: state.plans,
        profile: state.profile,
        tickets: state.tickets,
        carpools: state.carpools,
        myApplications: state.myApplications,
        keyDevices: state.keyDevices,
        digitalKeys: state.digitalKeys,
        masterKeys: state.masterKeys,
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
  state.cars = data.cars || [];
  state.members = data.members || [];
  state.reservations = data.reservations || [];
  state.users = data.users || [];
  state.plans = data.plans || [];
  state.profile = data.profile || state.profile;
  state.tickets = data.tickets || [];
  state.carpools = data.carpools || [];
  state.myApplications = data.my_applications ?? data.myApplications ?? [];
  state.keyDevices = data.key_devices ?? data.keyDevices ?? [];
  state.digitalKeys = data.digital_keys ?? data.digitalKeys ?? [];
  state.masterKeys = data.master_keys ?? data.masterKeys ?? [];
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
  renderPlanCard();
  renderBillingCard();
  renderCarpools();
  renderKeyDevices();
  renderMasterKeyPanel();
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

const weekdayFormatter = new Intl.DateTimeFormat('ja-JP', {
  weekday: 'short',
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

function formatYen(amount) {
  return `${Number(amount || 0).toLocaleString('ja-JP')}円`;
}

function currentMonthKey() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

function planByCode(code) {
  return state.plans.find((plan) => plan.code === code) || null;
}

function planLabel(code) {
  const plan = planByCode(code);
  return plan ? plan.name : code === 'none' ? '時間券のみ' : code;
}

function ticketSourceLabel(source) {
  return (
    {
      included: 'プラン付属',
      pack: '6時間パック',
      extra: '追加券',
    }[source] || source
  );
}

function ticketStatusLabel(status) {
  return (
    {
      available: '利用可能',
      reserved: '予約済み',
      used: '利用済み',
      expired: '期限切れ',
    }[status] || status
  );
}

function keyStatusLabel(status) {
  return (
    {
      scheduled: '発行待ち',
      pending: '発行中',
      issued: '発行済み',
      failed: '発行失敗',
      revoked: '失効',
      revoke_failed: '失効失敗',
      expired: '期限切れ',
    }[status] || status
  );
}

function applicationStatusLabel(status) {
  return (
    {
      pending: '申請中',
      accepted: '承認済み',
      rejected: '見送り',
      cancelled: 'キャンセル',
    }[status] || status
  );
}

function formatDateOnly(value) {
  const date = new Date(value);
  return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()}`;
}

function selectOptions(items, selectedValue, labeler, valueGetter = (item) => item.id) {
  return items
    .map((item) => {
      const value = valueGetter(item);
      const selected =
        String(value) === String(selectedValue) ? ' selected' : '';
      return `<option value="${esc(value)}"${selected}>${esc(labeler(item))}</option>`;
    })
    .join('');
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
  if (els.carpoolDialog?.open) els.carpoolDialog.close();
  stopCarpoolPolling();
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
  state.plans = [];
  state.profile = null;
  state.tickets = [];
  state.carpools = [];
  state.myApplications = [];
  state.keyDevices = [];
  state.digitalKeys = [];
  state.masterKeys = [];
  state.billing = null;
  state.billingUserId = '';
  state.reservationOptions = null;
  state.selectedPaymentType = 'time';
  state.currentUser = null;
  billingError = '';
  keyAuditLoaded = false;
  switchTab('home');
  showLogin();
  toast('ログアウトしました');
}

async function loadAll() {
  try {
    const data = await apiFetch('/state/');
    if (!data) throw new Error('状態を取得できませんでした');

    state.cars = data.cars || [];
    state.members = data.members || [];
    state.reservations = data.reservations || [];
    state.users = data.users || [];
    state.plans = data.plans || [];
    state.profile = data.profile || null;
    state.tickets = data.tickets || [];
    state.carpools = data.carpools || [];
    state.myApplications = data.my_applications || [];
    state.keyDevices = data.key_devices || [];
    state.digitalKeys = data.digital_keys || [];
    state.masterKeys = data.master_keys || [];
    if (data.profile) {
      state.currentUser = { ...(state.currentUser || {}), ...data.profile };
    }
    state.billing = null;
    billingError = '';
    keyAuditLoaded = false;

    renderAll();
    saveCachedState();
    startCarpoolPolling();
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

function memberDisplayName(member) {
  return member?.username || member?.name || '住人';
}

function memberOptionMarkup(members, selectedId) {
  const options = ['<option value="">なし</option>'];
  members.forEach((member) => {
    const selected = String(member.id) === String(selectedId) ? ' selected' : '';
    options.push(
      `<option value="${member.id}"${selected}>${esc(
        memberDisplayName(member)
      )}</option>`
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
            (member) =>
              `<option value="${member.id}">${esc(
                memberDisplayName(member)
              )}</option>`
          )
          .join('')
      : '<option value="">住人が登録されていません</option>';
  } else if (ownMember) {
    els.reserveMember.disabled = true;
    els.reserveMember.innerHTML = `<option value="${ownMember.id}">${esc(
      memberDisplayName(ownMember)
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

  updateReserveSubmitState();
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
          detail = `<strong>${esc(
            memberDisplayName(current.member)
          )}</strong> が利用中<br>${esc(
            formatRange(current.start_time, current.end_time)
          )}`;
        } else if (next) {
          detail = `次の予約：${esc(formatDateTime(next.start_time))}<br>利用者：<strong>${esc(
            memberDisplayName(next.member)
          )}</strong>`;
        } else {
          detail = '予約はありません';
        }

        return `
          <article class="car-card ${current ? 'is-busy' : ''}">
            <div class="car-top">
              <div>
                <div class="car-name">${esc(car.name)}</div>
                <div class="car-meta">${esc(car.color)} / ${esc(car.plate)} / 定員${esc(
                  car.seat_capacity || 4
                )}人${car.key_supported ? ' / デジタルキー対応' : ''}</div>
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

function isCarpoolRecruiting(rideShare, startTime) {
  return (
    rideShare?.status === 'open' &&
    new Date(startTime).getTime() > Date.now()
  );
}

function reservationCard(reservation, showActions) {
  const isUpcoming = new Date(reservation.end_time).getTime() > Date.now();
  const cancelButton =
    showActions && isUpcoming && canCancelReservation(reservation)
      ? `<button class="btn btn-danger btn-small" type="button" data-action="cancel-reservation" data-id="${reservation.id}">キャンセル</button>`
      : '';

  const charge = reservation.charge;
  const chargeLine = charge && charge.payment_type
    ? `<div class="reservation-meta">${
        charge.payment_type === 'ticket' ? '6時間券' :
        charge.payment_type === 'ticket_2' ? '6時間券×2' :
        charge.payment_type === 'ticket_overflow' ? '6時間券＋超過' :
        charge.payment_type === 'time_all' ? '時間料金' :
        '時間券'
      } / 今回の負担 ${formatYen(charge.actual_burden)}</div>`
    : '';
  const key = reservation.digital_key;
  const keyLine = key
    ? `<div class="reservation-meta reservation-meta--key">デジタルキー: ${esc(
        keyStatusLabel(key.status)
      )}（${esc(formatDateTime(key.valid_from))} 〜 ${esc(
        timeFormatter.format(new Date(key.valid_to))
      )}）</div>`
    : '';
  const carpoolRecruiting = isCarpoolRecruiting(
    reservation.ride_share,
    reservation.start_time
  );
  const carpoolBadge = carpoolRecruiting
    ? '<span class="carpool-badge carpool-badge--small">相乗り募集中</span>'
    : '';

  return `
    <article class="reservation-card${
      carpoolRecruiting ? ' has-carpool' : ''
    }" data-action="reservation-detail" data-id="${reservation.id}" data-date="${dateKey(new Date(reservation.start_time))}">
      <div class="reservation-main">
        <div class="reservation-title">
          ${esc(reservation.car?.name || '車')}
          <span class="chip">${esc(
            memberDisplayName(reservation.member)
          )}</span>
          ${carpoolBadge}
        </div>
        <div class="reservation-time">${esc(
          formatRange(reservation.start_time, reservation.end_time)
        )}</div>
        ${
          reservation.note
            ? `<div class="reservation-note">${esc(reservation.note)}</div>`
            : ''
        }
        ${chargeLine}
        ${keyLine}
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
    if (
      dayReservations.some((r) =>
        isCarpoolRecruiting(r.ride_share, r.start_time)
      )
    ) {
      classes.push('has-carpool');
    }

    const chips = dayReservations.slice(0, 3).map((reservation) => {
      const start = new Date(reservation.start_time);
      const dayStart = startOfDay(date);
      const timeLabel =
        start < dayStart ? '継続' : timeFormatter.format(start);
      const own = reservation.member_id === state.currentUser?.member_id;
      const carpool = isCarpoolRecruiting(
        reservation.ride_share,
        reservation.start_time
      );
      return `<span class="calendar-chip ${own ? 'is-own' : ''} ${
        carpool ? 'is-carpool' : ''
      }">${esc(timeLabel)} ${esc(reservation.car?.name || '車')}</span>`;
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
        <span class="calendar-day-weekday">${esc(weekdayFormatter.format(date))}</span>
        <span class="calendar-chips">${chips.join('')}</span>
      </button>
    `);
  }

  els.calendarGrid.innerHTML = cells.join('');
}

function renderCalendarDay() {
  const today = startOfDay(new Date());
  const dayReservations = reservationsForDay(today);
  els.selectedDayTitle.textContent = `今日（${dateFormatter.format(
    today
  )}）の予約`;
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
    .filter((reservation) => {
      const isOwner = reservation.member_id === state.currentUser?.member_id;
      if (isOwner) return true;
      const ride = reservation.ride_share;
      if (ride?.driver_user_id === state.currentUser?.id) return true;
      if (ride?.applications?.some(
        (a) => a.applicant_user_id === state.currentUser?.id && a.status === 'accepted'
      )) return true;
      return false;
    })
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

function openReservationDayModal(date) {
  console.debug('openReservationDayModal called', date);
  if (!els.reservationDayModal) {
    console.error('reservationDayModal element not found');
    return;
  }
  if (!date || isNaN(date.getTime())) {
    console.debug('invalid date', date);
    return;
  }
  els.modalDateTitle.textContent = `${selectedDayFormatter.format(date)}の予約`;
  renderReservationDayModal(date);
  els.reservationDayModal.showModal();
  console.debug('modal opened');
}

function closeReservationModal() {
  els.reservationDayModal.close();
}

function renderReservationDayModal(date) {
  const dayStart = startOfDay(date).getTime();
  const dayEnd = endOfDay(date).getTime();
  const now = Date.now();

  const dayReservations = state.reservations
    .filter((r) => {
      const start = new Date(r.start_time).getTime();
      const end = new Date(r.end_time).getTime();
      return start < dayEnd && end > dayStart;
    })
    .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());

  if (dayReservations.length === 0) {
    els.modalReservations.innerHTML = '<p class="muted">この日の予約はありません。</p>';
    return;
  }

  els.modalReservations.innerHTML = dayReservations.map((r) => {
    const isOwner = r.member_id === state.currentUser?.member_id;
    const start = new Date(r.start_time);
    const end = new Date(r.end_time);
    const durationMinutes = Math.round((end - start) / 60000);
    const durationHours = (durationMinutes / 60).toFixed(1);
    const charge = r.charge;
    const rideShare = r.ride_share;
    const isPast = end < now;

    let chargeHtml = '';
    if ((isOwner || isAdmin()) && charge) {
      const paymentLabel =
        charge.payment_type === 'ticket' ? '6時間券' :
        charge.payment_type === 'ticket_2' ? '6時間券×2' :
        charge.payment_type === 'ticket_overflow' ? '6時間券＋超過' :
        charge.payment_type === 'time_all' ? '時間料金' :
        charge.payment_type ? '時間券' : '-';
      chargeHtml = `<div class="reservation-detail-meta">${paymentLabel} / 負担 ${formatYen(charge.actual_burden)}</div>`;
    }

    let noteHtml = '';
    if (r.note) {
      const noteVisible = isOwner || isAdmin() || r.note_public;
      if (noteVisible) {
        noteHtml = `<div class="reservation-detail-note ${r.note_public ? 'public' : ''}">${esc(r.note)}</div>`;
      }
    }

    let keyHtml = '';
    if ((isOwner || isAdmin()) && r.digital_key) {
      keyHtml = `<div class="reservation-detail-meta">キー: ${keyStatusLabel(r.digital_key.status)}</div>`;
    }

    const carpoolBadge = isCarpoolRecruiting(rideShare, r.start_time)
      ? '<span class="carpool-badge"><svg class="icon" aria-hidden="true"><use href="#icon-people"></use></svg>相乗り募集中</span>'
      : '';

    const cancelBtn =
      (isOwner || isAdmin()) && !isPast
        ? `<button class="btn btn-danger btn-small cancel-detail-btn" type="button" data-action="cancel-reservation" data-id="${r.id}">キャンセル</button>`
        : '';

    return `
      <article class="reservation-detail-card ${isOwner ? 'is-own' : 'is-other'}" data-action="reservation-detail" data-id="${r.id}" data-date="${dateKey(date)}">
        <div class="reservation-detail-main">
          <div class="reservation-detail-title">
            ${esc(r.car?.name || '車')}
            ${carpoolBadge}
            <span class="chip">${esc(memberDisplayName(r.member))}</span>
          </div>
          <div class="reservation-detail-time">${formatRange(r.start_time, r.end_time)}（約${durationHours}時間）</div>
          ${chargeHtml}
          ${keyHtml}
          ${noteHtml}
        </div>
        <div class="reservation-detail-actions">
          ${cancelBtn}
        </div>
      </article>
    `;
  }).join('');
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
                <span>${esc(car.color)} / ${esc(car.plate)} / 定員${esc(
                  car.seat_capacity || 4
                )}人${car.key_supported ? ' / キー対応' : ''}</span>
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
                <strong>${esc(memberDisplayName(member))}</strong>
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
          const genderLabel =
            { male: '男性', female: '女性' }[user.gender] || '性別未設定';
          return `
            <div class="setting-row">
              <div class="setting-info">
                <strong>${esc(user.username)}</strong>
                <span><span class="role-badge role-badge--${user.role}">${roleLabel}</span> ${memberLabel} / ${esc(
                  planLabel(user.plan)
                )} / ${genderLabel}</span>
              </div>
              <div class="setting-actions">
                <button class="btn btn-ghost btn-small" type="button" data-action="grant-ticket" data-id="${
                  user.id
                }">例外付与</button>
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

let optionTimer = null;
let billingLoading = false;
let billingError = '';
let keyAuditLoaded = false;

function renderPlanCard() {
  if (!els.planCard) return;
  const profile = state.profile || state.currentUser || {};
  const plan = planByCode(profile.plan) || {
    name: '時間券のみ',
    monthly_fee: 0,
    included_tickets: 0,
    extra_six_hour_price: 4200,
    carry_over: false,
  };
  const extraPrice = plan.extra_six_hour_price ?? 4200;
  const tickets = Array.isArray(state.tickets) ? state.tickets : [];
  const available = tickets.filter(
    (ticket) => ticket.status === 'available'
  );
  const ticketRows = tickets.length
    ? tickets
        .slice(0, 8)
        .map(
          (ticket) => `
            <div class="ticket-row">
              <span>${esc(ticketSourceLabel(ticket.source))} #${esc(ticket.slot)}</span>
              <span>${esc(ticketStatusLabel(ticket.status))}</span>
              <small>${formatDateOnly(ticket.expires_at)}まで</small>
            </div>
          `
        )
        .join('')
    : '<p class="form-hint">利用できる6時間券はありません。管理者から付与できます。</p>';

  els.planCard.innerHTML = `
    <div class="section-head">
      <h2>料金プラン</h2>
      <span class="chip">${esc(plan.name)}</span>
    </div>
    <div class="stat-row"><span>月額</span><strong>${formatYen(plan.monthly_fee)}</strong></div>
    <div class="stat-row"><span>付属6時間券</span><strong>${esc(plan.included_tickets)}枚 / 月</strong></div>
    <div class="stat-row"><span>利用可能な券</span><strong>${available.length}枚</strong></div>
    <p class="form-hint">券は発行月の翌月末まで有効です。</p>
    <div class="ticket-list">${ticketRows}</div>
    <p class="form-hint">購入額は月別利用額に加算され、後精算になります。</p>
    <div class="form-actions">
      ${
        (profile.plan || 'none') === 'none'
          ? `<button class="btn btn-ghost btn-small" type="button" data-action="purchase-pack">6時間パックを購入（${formatYen(4200)}）</button>`
          : `<button class="btn btn-ghost btn-small" type="button" data-action="purchase-extra">追加6時間券を購入（${formatYen(extraPrice)}）</button>`
      }
    </div>
    <div class="section-head section-head--spaced">
      <h2>プラン・プロフィール</h2>
    </div>
    <div class="inline-controls">
      <select id="selfPlan">
        ${selectOptions(state.plans || [], profile.plan || 'none', (item) => `${item.name}（${formatYen(item.monthly_fee)}/月）`, (item) => item.code)}
      </select>
      <button class="btn btn-ghost btn-small" type="button" data-action="change-plan">プラン変更</button>
    </div>
    <div class="inline-controls">
      <select id="selfGender">
        <option value="">性別未設定</option>
        <option value="male" ${profile.gender === 'male' ? 'selected' : ''}>男性</option>
        <option value="female" ${profile.gender === 'female' ? 'selected' : ''}>女性</option>
      </select>
      <input id="selfRecipient" type="text" placeholder="キー受取人ID（任意）" value="${esc(profile.provider_recipient_id || '')}">
      <button class="btn btn-ghost btn-small" type="button" data-action="save-profile">保存</button>
    </div>
    <p class="form-hint">性別は相乗りの同性フィルターに使います。キー受取人IDはモックキー事業者への送信IDです。</p>
  `;
}

function renderBillingCard() {
  if (!els.billingCard) return;
  const month = state.billing?.month || currentMonthKey();
  const data = state.billing;
  const summary = data
    ? `
      <div class="stat-row"><span>プラン月額</span><strong>${formatYen(data.plan_fee)}</strong></div>
      <div class="stat-row"><span>券の購入</span><strong>${formatYen(data.ticket_purchases)}</strong></div>
      <div class="stat-row"><span>利用料</span><strong>${formatYen(data.usage_charges)}</strong></div>
      <div class="stat-row"><span>相乗り席代</span><strong>${formatYen(data.carpool_seat_fees_paid)}</strong></div>
      <div class="stat-row"><span>相乗り値引き</span><strong>-${formatYen(data.carpool_discount_received)}</strong></div>
      <div class="stat-row stat-row--total"><span>合計</span><strong>${formatYen(data.total)}</strong></div>
    `
    : billingError
      ? `<div class="empty">${esc(billingError)}</div>`
      : '<div class="empty">読み込み中...</div>';

  const entries = data?.entries?.length
    ? data.entries
        .slice(0, 12)
        .map(
          (entry) => `
            <div class="billing-row">
              <div><strong>${esc(entry.description)}</strong><small>${esc(entry.date)}</small></div>
              <span>${entry.amount < 0 ? '-' : ''}${formatYen(Math.abs(entry.amount))}</span>
            </div>
          `
        )
        .join('')
    : '';

  const users = Array.isArray(state.users) ? state.users : [];
  const userSelect = isAdmin()
    ? `<select id="billingUser">
        <option value="">自分</option>
        ${users
          .map(
            (user) =>
              `<option value="${user.id}" ${
                String(user.id) === String(state.billingUserId)
                  ? 'selected'
                  : ''
              }>${esc(user.username)}</option>`
          )
          .join('')}
      </select>`
    : '';

  els.billingCard.innerHTML = `
    <div class="section-head">
      <h2>月別利用額</h2>
    </div>
    <div class="inline-controls">
      ${userSelect}
      <input id="billingMonth" type="month" value="${esc(month)}">
      <button id="billingRefreshBtn" class="btn btn-ghost btn-small" type="button">表示</button>
    </div>
    <div class="billing-summary">${summary}</div>
    ${entries ? `<div class="billing-entries">${entries}</div>` : ''}
  `;

  $('#billingRefreshBtn')?.addEventListener('click', () => {
    loadBilling($('#billingMonth')?.value || currentMonthKey());
  });
  $('#billingUser')?.addEventListener('change', (event) => {
    state.billingUserId = event.target.value;
    state.billing = null;
    billingError = '';
    renderBillingCard();
  });

  if (!data && !billingError && !billingLoading) {
    void loadBilling(month);
  }
}

async function loadBilling(month) {
  if (billingLoading) return;
  billingLoading = true;
  billingError = '';
  try {
    const path = state.billingUserId
      ? `/billing/users/${state.billingUserId}?month=${encodeURIComponent(month)}`
      : `/billing/me?month=${encodeURIComponent(month)}`;
    const data = await apiFetch(path);
    if (!data) throw new Error('利用額を取得できませんでした');
    state.billing = data;
  } catch (error) {
    billingError = error.message;
  } finally {
    billingLoading = false;
    renderBillingCard();
  }
}

function renderReservationOptions(data) {
  if (!els.reservationOptions) return;
  if (!data || !Array.isArray(data.options)) {
    els.reservationOptions.innerHTML = '';
    els.reservationOptionsHint.textContent =
      '料金情報を取得できませんでした。もう一度お試しください。';
    updateReserveSubmitState();
    return;
  }
  if (data.blocked_reason) {
    els.reservationOptions.innerHTML = '';
    els.reservationOptionsHint.textContent = data.blocked_reason;
    updateReserveSubmitState();
    return;
  }

  if (!data.options.length) {
    els.reservationOptions.innerHTML = '';
    els.reservationOptionsHint.textContent = 'この日時は予約できません。';
    updateReserveSubmitState();
    return;
  }

  const validSelected = data.options.some(
    (option) => option.type === state.selectedPaymentType
  );
  if (!validSelected) {
    state.selectedPaymentType = data.options.some(
      (option) => option.type === 'time'
    )
      ? 'time'
      : data.options[0].type;
  }

  els.reservationOptions.innerHTML = data.options
    .map((option) => {
      const sourceLabel = ticketSourceLabel(option.ticket_source);
      const expiry = option.ticket_expires_at
        ? ` / 券の期限 ${formatDateOnly(option.ticket_expires_at)}`
        : '';
      let title;
      let detail;
      switch (option.type) {
        case 'ticket':
          title = `6時間券を使う（${sourceLabel}）`;
          detail = `今回の追加支払い ${formatYen(option.total)}${expiry}`;
          break;
        case 'ticket_2':
          title = '6時間券を2枚使う';
          detail = `今回の追加支払い ${formatYen(option.total)}${expiry}`;
          break;
        case 'ticket_overflow':
          title = `6時間券を使う（${sourceLabel}）＋超過分`;
          detail = `今回の支払い ${formatYen(option.total)}（超過分のみ）${expiry}`;
          break;
        case 'time_all':
          title = 'すべて時間料金（1時間700円）';
          detail = `今回の支払い ${formatYen(option.total)}（6時間券を使わない）`;
          break;
        default:
          title = '時間券（1時間700円）';
          detail = `今回の支払い ${formatYen(option.total)}`;
      }
      return `
        <label class="option-card">
          <input type="radio" name="payment_type" value="${option.type}" ${
            option.type === state.selectedPaymentType ? 'checked' : ''
          }>
          <span>
            <strong>${esc(title)}</strong>
            <small>${esc(detail)}</small>
          </span>
        </label>
      `;
    })
    .join('');
  els.reservationOptionsHint.textContent = data.hours
    ? `利用時間 ${data.hours}時間 / ${
        data.options.length > 1
          ? `${data.options.length}つの支払い方法から選べます`
          : '利用できる支払い方法は1つです'
      }`
    : '';
  updateReserveSubmitState();
}

function updateReserveSubmitState() {
  const admin = isAdmin();
  const ownMember = state.members.find(
    (member) => member.id === state.currentUser?.member_id
  );
  const noCars = state.cars.length === 0;
  const noMembers = admin ? state.members.length === 0 : !ownMember;
  const options = state.reservationOptions;
  const blocked = Boolean(options?.blocked_reason);
  const noOptions = Boolean(options && Array.isArray(options.options) && options.options.length === 0);

  els.reserveSubmit.disabled = noCars || noMembers || blocked || noOptions;
  if (blocked) {
    els.reserveSubmit.textContent = 'この日時は予約できません';
  } else if (noOptions) {
    els.reserveSubmit.textContent = '支払い方法がありません';
  } else if (noCars) {
    els.reserveSubmit.textContent = admin
      ? '先に車を登録してください'
      : '管理者に車の登録を依頼してください';
  } else if (noMembers) {
    els.reserveSubmit.textContent = admin
      ? '先に住人を登録してください'
      : '管理者に住人の紐付けを依頼してください';
  } else {
    els.reserveSubmit.textContent = '予約する';
  }
}

async function refreshReservationOptions(silent = false) {
  const carId = Number(els.reserveCar.value);
  const memberId = Number(els.reserveMember.value);
  const start = els.startTime.value;
  const end = els.endTime.value;
  const requestId = ++state.optionRequestId;

  if (!carId || !memberId || !start || !end) {
    state.reservationOptions = null;
    if (els.reservationOptions) {
      els.reservationOptions.innerHTML =
        '<p class="form-hint">車・利用者・日時を選ぶと料金が表示されます。</p>';
    }
    els.reservationOptionsHint.textContent = '';
    updateReserveSubmitState();
    return;
  }

  if (!silent) {
    els.reservationOptionsHint.textContent = '料金を計算しています...';
  }

  try {
    const data = await apiFetch('/reservations/options', {
      method: 'POST',
      body: JSON.stringify({
        car_id: carId,
        member_id: memberId,
        start_time: start,
        end_time: end,
      }),
    });
    if (requestId !== state.optionRequestId) return;
    state.reservationOptions = data;
    renderReservationOptions(data);
  } catch (error) {
    if (requestId !== state.optionRequestId) return;
    state.reservationOptions = null;
    if (els.reservationOptions) els.reservationOptions.innerHTML = '';
    els.reservationOptionsHint.textContent = error.message;
    updateReserveSubmitState();
  }
}

function scheduleOptionsRefresh() {
  clearTimeout(optionTimer);
  optionTimer = setTimeout(() => {
    void refreshReservationOptions(true);
  }, 350);
}

function carpoolCard(ride) {
  const admin = isAdmin();
  const isDriver = ride.driver_user_id === state.currentUser?.id;
  const applicationsList = Array.isArray(ride.applications)
    ? ride.applications
    : [];
  const myApplication = applicationsList.find(
    (application) =>
      application.applicant_user_id === state.currentUser?.id
  );
  const statusLabel =
    {
      open: '受付中',
      full: '満席',
      closed: '締切',
      cancelled: '中止',
    }[ride.status] || ride.status;
  const statusClass =
    ride.status === 'open'
      ? 'badge--free'
      : ride.status === 'cancelled'
        ? 'badge--busy'
        : 'badge--busy';
  const areaLabel = ride.area === 'far' ? '郊外' : '近場';
  const genderLabel =
    { any: '指定なし', male: '男性のみ', female: '女性のみ' }[
      ride.gender_filter
    ] || ride.gender_filter;

  const applications =
    isDriver || admin
      ? applicationsList
          .map(
            (application) => `
              <div class="carpool-application">
                <div>
                  <strong>${esc(application.applicant_name || '利用者')}</strong>
                  <small>${esc(
                    applicationStatusLabel(application.status)
                  )} / ${formatYen(application.seat_fee)}</small>
                </div>
                ${
                  application.status === 'pending'
                    ? `<div class="setting-actions">
                        <button class="btn btn-primary btn-small" type="button" data-action="approve-application" data-id="${ride.id}" data-application-id="${application.id}">承認</button>
                        <button class="btn btn-ghost btn-small" type="button" data-action="reject-application" data-id="${ride.id}" data-application-id="${application.id}">却下</button>
                      </div>`
                    : ''
                }
              </div>
            `
          )
          .join('')
      : '';

  let actionButtons = '';
  if (isDriver || admin) {
    if (ride.status !== 'cancelled') {
      actionButtons = `<button class="btn btn-danger btn-small" type="button" data-action="cancel-carpool" data-id="${ride.id}">募集を中止</button>`;
    }
  } else if (ride.status === 'open' && !myApplication) {
    actionButtons = `<button class="btn btn-primary btn-small" type="button" data-action="apply-carpool" data-id="${ride.id}">申し込む</button>`;
  } else if (
    myApplication &&
    ['pending', 'accepted'].includes(myApplication.status)
  ) {
    actionButtons = `
      <span class="chip">${myApplication.status === 'pending' ? '申請中' : '参加確定'}</span>
      <button class="btn btn-ghost btn-small" type="button" data-action="cancel-application" data-id="${ride.id}">取り消す</button>
    `;
  } else if (myApplication?.status === 'rejected') {
    const canReapply = ride.remaining_seats > 0 && ride.status === 'open';
    actionButtons = `
      <span class="chip">見送り</span>
      ${
        canReapply
          ? `<button class="btn btn-primary btn-small" type="button" data-action="apply-carpool" data-id="${ride.id}">再申し込み</button>`
          : ''
      }
    `;
  } else if (ride.remaining_seats > 0 && ride.status === 'open') {
    actionButtons = `<button class="btn btn-primary btn-small" type="button" data-action="apply-carpool" data-id="${ride.id}">申し込む</button>`;
  }

  return `
    <article class="carpool-card">
      <div class="carpool-top">
        <div>
          <strong>${esc(ride.car_name || '車')}</strong>
          <span class="chip">運転手: ${esc(ride.driver_name || '不明')}</span>
        </div>
        <span class="badge ${statusClass}">${esc(statusLabel)}</span>
      </div>
      <div class="reservation-time">${esc(
        formatRange(ride.start_time, ride.end_time)
      )}</div>
      <div class="carpool-meta">${esc(areaLabel)} / ${formatYen(
        ride.seat_fee
      )} / 残り${esc(ride.remaining_seats)}席 / ${esc(genderLabel)}</div>
      ${ride.note ? `<div class="reservation-note">${esc(ride.note)}</div>` : ''}
      ${applications ? `<div class="carpool-applications">${applications}</div>` : ''}
      ${actionButtons ? `<div class="reservation-actions">${actionButtons}</div>` : ''}
    </article>
  `;
}

function renderCarpools() {
  if (!els.carpoolList) return;
  const now = Date.now();
  const admin = isAdmin();
  const ownMemberId = state.currentUser?.member_id;
  const rides = (Array.isArray(state.carpools) ? state.carpools : []).filter(
    (ride) =>
      ride.status !== 'cancelled' &&
      ride.start_time &&
      new Date(ride.start_time).getTime() > now
  );
  const reservations = Array.isArray(state.reservations)
    ? state.reservations
    : [];
  const usedReservationIds = new Set(
    rides.map((ride) => ride.reservation_id)
  );
  const candidates = reservations.filter(
    (reservation) =>
      new Date(reservation.end_time).getTime() > now &&
      !usedReservationIds.has(reservation.id) &&
      (admin || reservation.member_id === ownMemberId)
  );
  const selected = els.carpoolReservation.value;
  els.carpoolReservation.innerHTML = candidates.length
    ? candidates
        .map(
          (reservation) =>
            `<option value="${reservation.id}">${esc(
              formatRange(reservation.start_time, reservation.end_time)
            )} / ${esc(reservation.car.name)}</option>`
        )
        .join('')
    : '<option value="">募集できる予約がありません</option>';
  if (candidates.some((reservation) => String(reservation.id) === selected)) {
    els.carpoolReservation.value = selected;
  }

  els.carpoolList.innerHTML = rides.length
    ? rides.map(carpoolCard).join('')
    : emptyState('相乗り募集はありません');

  renderCarpoolBadge();
  if (
    state.activeTab === 'carpool' &&
    document.visibilityState === 'visible'
  ) {
    markApplicantCarpoolSeen();
    renderCarpoolBadge();
  }
}

function carpoolSeenKey() {
  const userId = state.currentUser?.id;
  return userId ? `${CARPOOL_SEEN_KEY_PREFIX}${userId}` : '';
}

function readCarpoolSeen() {
  const key = carpoolSeenKey();
  if (!key) return {};
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '{}');
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (_) {
    return {};
  }
}

function writeCarpoolSeen(seen) {
  const key = carpoolSeenKey();
  if (!key) return;
  try {
    localStorage.setItem(key, JSON.stringify(seen));
  } catch (_) {
    // 保存できなくても通知表示は継続する
  }
}

function carpoolApplicationSignature(application) {
  return `${application.status}:${application.decided_at || ''}`;
}

function carpoolNotificationCount() {
  const userId = state.currentUser?.id;
  if (!userId) return 0;
  const seen = readCarpoolSeen();
  let count = 0;

  (state.carpools || []).forEach((ride) => {
    const applications = Array.isArray(ride.applications)
      ? ride.applications
      : [];
    if (ride.driver_user_id === userId) {
      count += applications.filter(
        (application) => application.status === 'pending'
      ).length;
    }

    const mine = applications.find(
      (application) => application.applicant_user_id === userId
    );
    if (
      mine &&
      ['accepted', 'rejected'].includes(mine.status) &&
      seen[mine.id] !== carpoolApplicationSignature(mine)
    ) {
      count += 1;
    }
  });

  return count;
}

function renderCarpoolBadge() {
  const count = carpoolNotificationCount();
  $$('[data-carpool-badge]').forEach((badge) => {
    badge.hidden = count === 0;
    badge.textContent = count > 9 ? '9+' : String(count);
    badge.setAttribute('aria-label', `${count}件の相乗り通知`);
  });
}

function markApplicantCarpoolSeen() {
  const userId = state.currentUser?.id;
  if (!userId) return;
  const seen = readCarpoolSeen();
  let changed = false;

  (state.carpools || []).forEach((ride) => {
    (ride.applications || []).forEach((application) => {
      if (application.applicant_user_id !== userId) return;
      if (!['accepted', 'rejected'].includes(application.status)) return;
      const signature = carpoolApplicationSignature(application);
      if (seen[application.id] !== signature) {
        seen[application.id] = signature;
        changed = true;
      }
    });
  });

  if (changed) writeCarpoolSeen(seen);
}

async function refreshCarpoolState() {
  if (!state.currentUser) return;
  if (carpoolRefreshPromise) return carpoolRefreshPromise;

  carpoolRefreshPromise = (async () => {
    try {
      const data = await apiFetch('/carpools/');
      if (!Array.isArray(data)) return;
      state.carpools = data;
      renderCarpools();
    } catch (error) {
      if (error.message !== 'unauthorized') {
        // 自動更新の失敗は静かに無視する
      }
    } finally {
      carpoolRefreshPromise = null;
    }
  })();

  return carpoolRefreshPromise;
}

function startCarpoolPolling() {
  stopCarpoolPolling();
  carpoolPollTimer = setInterval(() => {
    if (document.visibilityState === 'visible') {
      void refreshCarpoolState();
    }
  }, CARPOOL_POLL_MS);
}

function stopCarpoolPolling() {
  if (!carpoolPollTimer) return;
  clearInterval(carpoolPollTimer);
  carpoolPollTimer = null;
}

function openCarpoolDialog() {
  if (!els.carpoolDialog) return;
  renderCarpools();
  if (!els.carpoolReservation.value) {
    toast('募集できる予約がありません', true);
    return;
  }
  els.carpoolDialog.showModal();
}

function renderKeyDevices() {
  if (!els.keyDeviceList) return;
  const selectedCar = els.keyDeviceCar.value;
  const cars = Array.isArray(state.cars) ? state.cars : [];
  const devices = Array.isArray(state.keyDevices) ? state.keyDevices : [];
  els.keyDeviceCar.innerHTML = cars.length
    ? selectOptions(cars, selectedCar, (car) => car.name)
    : '<option value="">車がありません</option>';

  els.keyDeviceList.innerHTML = devices.length
    ? devices
        .map(
          (device) => `
            <div class="setting-row">
              <div class="setting-info">
                <strong>${esc(device.car_name || '車')}</strong>
                <span>${esc(device.provider)} / ${esc(
                  device.provider_device_id
                )} / ${esc(device.status)}${
                  device.last_synced_at
                    ? ` / 同期 ${esc(formatDateTime(device.last_synced_at))}`
                    : ''
                }</span>
              </div>
              <div class="setting-actions">
                <button class="btn btn-ghost btn-small" type="button" data-action="sync-key-device" data-id="${device.id}">同期</button>
                <button class="btn btn-danger btn-small" type="button" data-action="deactivate-key-device" data-id="${device.id}">停止</button>
              </div>
            </div>
          `
        )
        .join('')
    : emptyState('キーボックスは未登録です');
}

function renderMasterKeyPanel() {
  if (!els.masterKeyList) return;
  if (!isAdmin()) {
    els.masterKeyCar.innerHTML = '';
    els.masterKeyList.innerHTML = '';
    els.keyAuditList.innerHTML = '';
    return;
  }
  const selectedCar = els.masterKeyCar.value;
  const cars = Array.isArray(state.cars) ? state.cars : [];
  const masterKeys = Array.isArray(state.masterKeys) ? state.masterKeys : [];
  els.masterKeyCar.innerHTML = cars.length
    ? selectOptions(cars, selectedCar, (car) => car.name)
    : '<option value="">車がありません</option>';

  els.masterKeyList.innerHTML = masterKeys.length
    ? masterKeys
        .slice(0, 8)
        .map((key) => {
          const car = cars.find((item) => item.id === key.car_id);
          return `
            <div class="setting-row">
              <div class="setting-info">
                <strong>${esc(car?.name || `車ID ${key.car_id}`)} / ${esc(
                  keyStatusLabel(key.status)
                )}</strong>
                <span>${esc(formatDateTime(key.valid_from))} 〜 ${esc(
                  formatDateTime(key.valid_to)
                )} / ${esc(key.reason || '理由なし')}${
                  key.was_in_use ? ' / 利用中に発行' : ''
                }</span>
              </div>
              ${
                key.status !== 'revoked'
                  ? `<div class="setting-actions"><button class="btn btn-ghost btn-small" type="button" data-action="revoke-key" data-id="${key.id}">失効</button></div>`
                  : ''
              }
            </div>
          `;
        })
        .join('')
    : emptyState('マスターキーの履歴はありません');

  if (!keyAuditLoaded) {
    keyAuditLoaded = true;
    void loadKeyAudit();
  }
}

async function loadKeyAudit() {
  if (!isAdmin() || !els.keyAuditList) return;
  els.keyAuditList.innerHTML = '<div class="empty">読み込み中...</div>';
  try {
    const events =
      (await apiFetch('/digital-keys/audit?limit=20')) || [];
    els.keyAuditList.innerHTML = events.length
      ? events
          .map(
            (event) => `
              <div class="audit-row">
                <div>
                  <strong>${esc(event.action)} / ${esc(event.result)}</strong>
                  <small>${esc(formatDateTime(event.created_at))} / ${
                    event.actor_name ? esc(event.actor_name) : 'システム'
                  } / ${esc(event.reason || '理由なし')}</small>
                </div>
                <span class="chip">車ID ${esc(event.car_id)}</span>
              </div>
            `
          )
          .join('')
      : emptyState('監査ログはありません');
  } catch (error) {
    els.keyAuditList.innerHTML = `<div class="empty">${esc(error.message)}</div>`;
  }
}

async function purchasePack() {
  if (
    !window.confirm(
      '6時間パックを4,200円で購入しますか？購入額は今月の利用額に加算されます。'
    )
  ) {
    return;
  }
  try {
    await apiFetch('/tickets/purchase', {
      method: 'POST',
      body: JSON.stringify({ source: 'pack', count: 1 }),
    });
    toast('6時間パックを購入しました（今月の利用額に加算）');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function purchaseExtraTicket() {
  const plan = planByCode(state.profile?.plan || state.currentUser?.plan);
  const price = plan?.extra_six_hour_price ?? 4200;
  if (
    !window.confirm(
      `追加6時間券を${formatYen(price)}で購入しますか？購入額は今月の利用額に加算されます。`
    )
  ) {
    return;
  }
  try {
    await apiFetch('/tickets/purchase', {
      method: 'POST',
      body: JSON.stringify({ source: 'extra', count: 1 }),
    });
    toast('追加6時間券を購入しました（今月の利用額に加算）');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function changePlan() {
  const userId = state.currentUser?.id;
  const plan = $('#selfPlan')?.value;
  if (!userId || !plan) return;
  if (!window.confirm('料金プランを変更しますか？')) return;
  try {
    await apiFetch(`/users/${userId}/plan`, {
      method: 'PUT',
      body: JSON.stringify({ plan }),
    });
    toast('料金プランを変更しました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function saveMyProfile() {
  const userId = state.currentUser?.id;
  if (!userId) return;
  try {
    await apiFetch(`/users/${userId}/profile`, {
      method: 'PUT',
      body: JSON.stringify({
        gender: $('#selfGender')?.value || 'unspecified',
        provider_recipient_id: $('#selfRecipient')?.value.trim() || null,
      }),
    });
    toast('プロフィールを保存しました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function grantTicket(userId) {
  const countText = window.prompt(
    '例外付与する追加6時間券の枚数（1〜10）',
    '1'
  );
  if (countText === null) return;
  const count = Number(countText);
  if (!Number.isInteger(count) || count < 1 || count > 10) {
    toast('1〜10の整数を入力してください', true);
    return;
  }
  try {
    await apiFetch(`/users/${userId}/tickets`, {
      method: 'POST',
      body: JSON.stringify({ source: 'extra', count }),
    });
    toast('追加6時間券を例外付与しました（利用額に加算）');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function applyCarpool(rideId) {
  try {
    await apiFetch(`/carpools/${rideId}/apply`, { method: 'POST' });
    toast('相乗りに申し込みました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function cancelMyApplication(rideId) {
  if (!window.confirm('この相乗りの申し込みを取り消しますか？')) return;
  try {
    await apiFetch(`/carpools/${rideId}/applications`, { method: 'DELETE' });
    toast('申し込みを取り消しました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function approveApplication(rideId, applicationId) {
  try {
    await apiFetch(
      `/carpools/${rideId}/applications/${applicationId}/approve`,
      { method: 'POST' }
    );
    toast('申し込みを承認しました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function rejectApplication(rideId, applicationId) {
  try {
    await apiFetch(
      `/carpools/${rideId}/applications/${applicationId}/reject`,
      { method: 'POST' }
    );
    toast('申し込みを却下しました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function cancelCarpool(rideId) {
  if (!window.confirm('この相乗り募集を中止しますか？')) return;
  try {
    await apiFetch(`/carpools/${rideId}`, { method: 'DELETE' });
    toast('相乗り募集を中止しました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function syncKeyDevice(deviceId) {
  try {
    await apiFetch(`/key-devices/${deviceId}/sync`, { method: 'POST' });
    toast('キーボックスの状態を同期しました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function deactivateKeyDevice(deviceId) {
  if (!window.confirm('このキーボックスを停止しますか？')) return;
  try {
    await apiFetch(`/key-devices/${deviceId}`, { method: 'DELETE' });
    toast('キーボックスを停止しました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function revokeDigitalKey(keyId) {
  if (!window.confirm('このデジタルキーを失効しますか？')) return;
  try {
    await apiFetch(`/digital-keys/${keyId}/revoke`, { method: 'POST' });
    toast('デジタルキーを失効しました');
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function issueMasterKey() {
  const carId = Number(els.masterKeyCar.value);
  const password = els.masterPassword.value;
  const reason = els.masterReason.value.trim();
  if (!carId) {
    toast('車を選択してください', true);
    return;
  }
  if (!password || !reason) {
    toast('管理者パスワードと理由を入力してください', true);
    return;
  }
  if (!window.confirm('マスターキーを発行しますか？')) return;
  try {
    const key = await apiFetch(`/digital-keys/cars/${carId}/master`, {
      method: 'POST',
      body: JSON.stringify({
        password,
        reason,
        confirm_in_use: els.masterConfirmInUse.checked,
      }),
    });
    els.masterPassword.value = '';
    await loadAll();
    els.masterKeyResult.textContent = `マスターキー: ${keyStatusLabel(
      key.status
    )} / ${formatDateTime(key.valid_from)} 〜 ${formatDateTime(
      key.valid_to
    )}${key.last_error ? ` / ${key.last_error}` : ''}`;
    if (key.status === 'issued') {
      toast('マスターキーを発行しました');
    } else {
      toast(`マスターキーの発行に失敗しました: ${key.last_error}`, true);
    }
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function remoteUnlock() {
  const carId = Number(els.masterKeyCar.value);
  const password = els.masterPassword.value;
  const reason = els.masterReason.value.trim();
  if (!carId) {
    toast('車を選択してください', true);
    return;
  }
  if (!password || !reason) {
    toast('管理者パスワードと理由を入力してください', true);
    return;
  }
  if (!window.confirm('遠隔解錠を実行しますか？')) return;
  try {
    const result = await apiFetch(
      `/digital-keys/cars/${carId}/remote-unlock`,
      {
        method: 'POST',
        body: JSON.stringify({
          password,
          reason,
          confirm_in_use: els.masterConfirmInUse.checked,
        }),
      }
    );
    els.masterPassword.value = '';
    els.masterKeyResult.textContent = result.ok
      ? '遠隔解錠を実行しました（モック）'
      : '遠隔解錠に失敗しました';
    toast(result.ok ? '遠隔解錠を実行しました' : '遠隔解錠に失敗しました', !result.ok);
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
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
  if (tab === 'carpool') {
    renderCarpools();
    void refreshCarpoolState();
  }
  if (tab === 'home') {
    renderBillingCard();
  }
  if (tab === 'settings') {
    renderKeyDevices();
    renderMasterKeyPanel();
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
  els.editCarSeatCapacity.value = car.seat_capacity || 4;
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
  els.editUserPlan.value = user.plan || 'none';
  els.editUserGender.value = user.gender || 'unspecified';
  els.editUserRecipient.value = user.provider_recipient_id || '';
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
    const reservation = state.reservations.find((r) => r.id === reservationId);
    const rideShare = reservation?.ride_share;
    const hasAcceptedCarpool =
      rideShare &&
      (rideShare.status === 'open' ||
        rideShare.applications?.some((a) => a.status === 'accepted'));
    await apiFetch(`/reservations/${reservationId}`, { method: 'DELETE' });
    if (hasAcceptedCarpool) {
      toast('予約をキャンセルしました（相乗り参加者にも通知されます）');
    } else {
      toast('予約をキャンセルしました');
    }
    await loadAll();
  } catch (error) {
    if (error.message !== 'unauthorized') toast(error.message, true);
  }
}

async function handleAction(action, id, dataset = {}) {
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
    case 'reservation-detail':
      console.debug('reservation-detail clicked', dataset);
      void openReservationDayModal(new Date(dataset.date || ''));
      break;
    case 'purchase-pack':
      await purchasePack();
      break;
    case 'purchase-extra':
      await purchaseExtraTicket();
      break;
    case 'change-plan':
      await changePlan();
      break;
    case 'save-profile':
      await saveMyProfile();
      break;
    case 'grant-ticket':
      await grantTicket(id);
      break;
    case 'apply-carpool':
      await applyCarpool(id);
      break;
    case 'cancel-application':
      await cancelMyApplication(id);
      break;
    case 'approve-application':
      await approveApplication(id, Number(dataset.applicationId || 0));
      break;
    case 'reject-application':
      await rejectApplication(id, Number(dataset.applicationId || 0));
      break;
    case 'cancel-carpool':
      await cancelCarpool(id);
      break;
    case 'sync-key-device':
      await syncKeyDevice(id);
      break;
    case 'deactivate-key-device':
      await deactivateKeyDevice(id);
      break;
    case 'revoke-key':
      await revokeDigitalKey(id);
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
    console.debug('calendar cell clicked', dayButton.dataset.calendarDate);
    selectCalendarDate(parseDateKey(dayButton.dataset.calendarDate));
    void openReservationDayModal(parseDateKey(dayButton.dataset.calendarDate));
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
    const submitButton = els.reservationForm.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    try {
      await refreshReservationOptions(true);
      if (state.reservationOptions?.blocked_reason) {
        toast(state.reservationOptions.blocked_reason, true);
        return;
      }
      if (!state.reservationOptions?.options?.length) {
        toast('この日時は予約できません', true);
        return;
      }

      const payload = {
        car_id: Number(els.reserveCar.value),
        member_id: Number(els.reserveMember.value),
        start_time: els.startTime.value,
        end_time: els.endTime.value,
        note: els.note.value.trim(),
        note_public: els.notePublic.checked,
        payment_type: state.selectedPaymentType,
      };

      await apiFetch('/reservations/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      els.note.value = '';
      els.notePublic.checked = false;
      state.reservationOptions = null;
      state.selectedPaymentType = 'time';
      updateReserveSubmitState();
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
    scheduleOptionsRefresh();
  });

  els.endTime.addEventListener('change', scheduleOptionsRefresh);
  els.reserveCar.addEventListener('change', scheduleOptionsRefresh);
  els.reserveMember.addEventListener('change', scheduleOptionsRefresh);
  els.refreshOptionsBtn.addEventListener('click', () => {
    clearTimeout(optionTimer);
    state.reservationOptions = null;
    if (els.reservationOptions) els.reservationOptions.innerHTML = '';
    void refreshReservationOptions();
  });
  els.reservationOptions.addEventListener('change', (event) => {
    const input = event.target.closest('input[name="payment_type"]');
    if (!input) return;
    state.selectedPaymentType = input.value;
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
          seat_capacity: Number(els.carSeatCapacity.value) || 4,
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
          seat_capacity: Number(els.editCarSeatCapacity.value) || 4,
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
      await apiFetch(`/users/${userId}/plan`, {
        method: 'PUT',
        body: JSON.stringify({ plan: els.editUserPlan.value }),
      });
      await apiFetch(`/users/${userId}/profile`, {
        method: 'PUT',
        body: JSON.stringify({
          gender: els.editUserGender.value,
          provider_recipient_id: els.editUserRecipient.value.trim() || null,
        }),
      });
      els.userDialog.close();
      toast('ユーザーを更新しました');
      await loadAll();
    } catch (error) {
      if (error.message !== 'unauthorized') toast(error.message, true);
    }
  });

  els.openCarpoolDialogBtn?.addEventListener('click', openCarpoolDialog);

  els.carpoolForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const reservationId = Number(els.carpoolReservation.value);
    if (!reservationId) {
      toast('対象の予約がありません', true);
      return;
    }
    try {
      await apiFetch('/carpools/', {
        method: 'POST',
        body: JSON.stringify({
          reservation_id: reservationId,
          area: els.carpoolArea.value,
          gender_filter: els.carpoolGender.value,
          seats_offered: Number(els.carpoolSeats.value) || 1,
          driver_guest_seats: Number(els.carpoolGuestSeats.value) || 0,
          note: els.carpoolNote.value.trim(),
          note_public: els.carpoolNotePublic.checked,
        }),
      });
      els.carpoolNote.value = '';
      els.carpoolNotePublic.checked = false;
      els.carpoolDialog?.close();
      toast('相乗り募集を作成しました');
      await loadAll();
    } catch (error) {
      if (error.message !== 'unauthorized') toast(error.message, true);
    }
  });

  els.keyDeviceForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const carId = Number(els.keyDeviceCar.value);
    if (!carId) {
      toast('車を選択してください', true);
      return;
    }
    try {
      await apiFetch('/key-devices/', {
        method: 'POST',
        body: JSON.stringify({
          car_id: carId,
          provider: 'mock',
          provider_device_id: els.keyDeviceId.value.trim(),
          display_name: els.keyDeviceName.value.trim(),
        }),
      });
      els.keyDeviceForm.reset();
      toast('キーボックスを登録しました');
      await loadAll();
    } catch (error) {
      if (error.message !== 'unauthorized') toast(error.message, true);
    }
  });

  els.masterKeyBtn.addEventListener('click', () => {
    void issueMasterKey();
  });
  els.remoteUnlockBtn.addEventListener('click', () => {
    void remoteUnlock();
  });
  els.keyAuditRefresh.addEventListener('click', () => {
    keyAuditLoaded = true;
    void loadKeyAudit();
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
      void handleAction(
        actionButton.dataset.action,
        Number(actionButton.dataset.id || 0),
        actionButton.dataset
      );
      return;
    }

    const closeButton = event.target.closest('[data-close-dialog]');
    if (closeButton) {
      document.getElementById(closeButton.dataset.closeDialog)?.close();
    }
  });

  [els.carDialog, els.memberDialog, els.userDialog, els.carpoolDialog, els.reservationDayModal]
    .filter(Boolean)
    .forEach((dialog) => {
      dialog.addEventListener('click', (event) => {
        if (event.target === dialog) dialog.close();
      });
    });

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && state.currentUser) {
      void refreshCarpoolState();
    }
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
