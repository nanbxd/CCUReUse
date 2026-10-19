import { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Check, ChevronRight, Clock3, Heart, Leaf, MapPin, Menu, Moon, Sun, Plus, Search, SlidersHorizontal, UserRound, X, Package, LogOut, Edit3, ExternalLink, Camera, Gift, Recycle, ShoppingBag, CalendarDays, ArrowUpRight } from 'lucide-react'
import { api, categories } from './api'
import { Events, EventDetail, CreateEvent, MyTickets, Organizer } from './Events'
import collegeLogo from './logos/logo.png'
import HubHome from './HubHome'
import { ListingCard as ItemCard, priceText } from './ListingCard'
import telegramLogo from './logos/telegramlogo.svg'

const statusLabels = { available: 'Доступно', reserved: 'Забронировано', given: 'Продано / передано', pending: 'На модерации' }
const dateText = value => new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
const timeAgo = value => {
  const hours = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 3600000))
  if (hours < 1) return 'Только что'
  if (hours < 24) return `${hours} ч назад`
  const days = Math.floor(hours / 24)
  return days === 1 ? 'Вчера' : `${days} дн назад`
}
const initials = name => (name || 'C').split(' ').map(x => x[0]).slice(0, 2).join('').toUpperCase()
const studentInfo = person => [person.education_level === 'college' ? 'Колледж' : person.education_level === 'university' ? 'Университет' : 'Участник CaspianHub', person.study_group ? `группа ${person.study_group}` : ''].filter(Boolean).join(' · ')

function useItems(params = '') {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setLoading(true)
    api(`/listings${params}`).then(data => { if (active) { setItems(data); setError('') } }).catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [params])
  return { items, loading, error }
}

function Brand({ light = false }) {
  return <Link to="/" className={`brand ${light ? 'brand-light' : ''}`} aria-label="CaspianHub — главная">
    <img className="brand-logo" src={collegeLogo} alt="" /><span className="hub-wordmark">Caspian<span>Hub</span><small>СООБЩЕСТВО CASPIAN</small></span>
  </Link>
}

function Header({ user, theme, onThemeToggle }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const navigate = useNavigate()
  const close = () => setMenuOpen(false)
  return <header className="site-header">
    <div className="container header-inner">
      <Brand />
      <nav className={`main-nav ${menuOpen ? 'open' : ''}`} aria-label="Главное меню">
        <NavLink onClick={close} end to="/">Главная</NavLink>
        <NavLink onClick={close} to="/market">Маркет</NavLink>
        <NavLink onClick={close} to="/events">Афиша</NavLink>
        <NavLink onClick={close} to="/support">Поддержка</NavLink>
        {user?.is_admin && <NavLink onClick={close} to="/admin">Админ</NavLink>}
      </nav>
      <div className="header-actions">
        <button className="btn btn-primary btn-sm header-add" onClick={() => navigate('/publish')}><Plus size={18} /> Создать</button>
        <button className="theme-toggle" type="button" onClick={onThemeToggle} aria-label={theme === 'dark' ? 'Включить светлую тему' : 'Включить тёмную тему'} title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}>{theme === 'dark' ? <Sun size={19} /> : <Moon size={19} />}</button>
        <Link className="header-account" to={user ? '/profile' : '/auth'} title={user ? 'Мой профиль' : 'Войти'}><UserRound size={19} /><span>{user ? user.name.split(' ')[0] : 'Войти'}</span></Link>
        <button className="mobile-menu" aria-expanded={menuOpen} aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X /> : <Menu />}</button>
      </div>
    </div>
  </header>
}

function Footer() {
  return <footer className="footer hub-footer"><div className="container footer-grid">
    <div><Brand light /><p>Всё, что объединяет Caspian.<br />Одна платформа для жизни сообщества.</p></div>
    <div><b>Открывай</b><Link to="/events">Афиша событий</Link><Link to="/market">Маркет</Link><Link to="/profile/tickets">Мои билеты</Link></div>
    <div><b>Участвуй</b><Link to="/events/new">Создать мероприятие</Link><Link to="/market/new">Разместить объявление</Link><Link to="/organizer">Кабинет организатора</Link></div>
    <div><b>CaspianHub</b><Link to="/about">О платформе</Link><Link to="/support">Поддержка</Link><a href="https://cu.edu.kz/" target="_blank" rel="noreferrer">Caspian University <ExternalLink size={12} /></a></div>
  </div><div className="container footer-bottom"><span>© 2026 CaspianHub. Сделано студентами для студентов.</span><span>Алматы, Казахстан</span></div></footer>
}

function Empty({ title = 'Пока ничего нет', text = 'Попробуйте другую категорию или загляните позже.' }) {
  return <div className="empty"><span><Package size={30} /></span><h3>{title}</h3><p>{text}</p></div>
}

function Catalog() {
  const [searchParams, setSearchParams] = useSearchParams()
  const category = searchParams.get('category') || 'Все'
  const q = searchParams.get('q') || ''
  const priceType = searchParams.get('price_type') || 'all'
  const [input, setInput] = useState(q)
  useEffect(() => setInput(q), [q])
  const params = useMemo(() => `?${new URLSearchParams({ ...(category !== 'Все' ? { category } : {}), ...(q ? { q } : {}), price_type: priceType, limit: '100' })}`, [category, q, priceType])
  const { items, loading, error } = useItems(params)
  const setCategory = value => setSearchParams({ price_type: priceType, ...(value !== 'Все' ? { category: value } : {}), ...(q ? { q } : {}) })
  const submit = e => { e.preventDefault(); setSearchParams({ price_type: priceType, ...(category !== 'Все' ? { category } : {}), ...(input.trim() ? { q: input.trim() } : {}) }) }
  return <main className="page"><div className="page-hero catalog-hero"><div className="container"><span className="section-label">МАРКЕТ CASPIANHUB</span><h1>Маркет<span className="accent-dot">.</span></h1><p>Покупайте, продавайте и отдавайте вещи внутри сообщества Caspian.</p></div></div><div className="container catalog-content"><div className="catalog-toolbar"><form className="search-box" onSubmit={submit}><Search size={20} /><input value={input} onChange={e => setInput(e.target.value)} placeholder="Что ищешь? Например, учебник или рюкзак" aria-label="Поиск вещей" /><button type="submit">Найти <ArrowRight size={17} /></button></form><span className="catalog-count">{loading ? 'Загрузка...' : `${items.length} ${items.length === 1 ? 'вещь' : 'вещей'}`}</span></div><div className="market-payment-filter" role="group" aria-label="Стоимость"><span>Стоимость</span>{[['all', 'Все объявления'], ['free', 'Бесплатно'], ['paid', 'Платно']].map(([value,label]) => <button key={value} className={`chip ${priceType === value ? 'active' : ''}`} aria-pressed={priceType === value} onClick={() => setSearchParams({ ...(category !== 'Все' ? { category } : {}), ...(q ? { q } : {}), price_type: value })}>{label}</button>)}<Link className="text-link" to="/market/new"><Plus size={16} /> Разместить объявление</Link></div><div className="filter-row"><span className="filter-label"><SlidersHorizontal size={17} /> Категории</span><div className="filter-chips">{categories.map(name => <button className={`chip ${category === name ? 'active' : ''}`} onClick={() => setCategory(name)} key={name}>{name}</button>)}</div></div>{error ? <div className="notice error">{error}</div> : loading ? <div className="loading">Загружаем маркет...</div> : items.length ? <div className="item-grid catalog-grid">{items.map(item => <ItemCard item={item} key={item.id} />)}</div> : <Empty title="Ничего не нашлось" text="Попробуй другой запрос или категорию — новые вещи появляются постоянно." />}</div></main>
}

function Feed() {
  const { items, loading, error } = useItems('?limit=100')
  return <main className="page feed-page"><div className="page-hero feed-hero"><div className="container"><span className="section-label">ЛЕНТА СООБЩЕСТВА</span><h1>Новое в маркете<span className="accent-dot">.</span></h1><p>Листай, вдохновляйся и находи вещи с историей.</p></div></div><div className="container feed-layout"><div className="feed-main"><div className="feed-heading"><div className="live-dot" /><h2>Свежие публикации</h2><span>Сначала новые</span></div>{error ? <div className="notice error">{error}</div> : loading ? <div className="loading">Загружаем ленту...</div> : items.length ? items.map(item => <article className="feed-post" key={item.id}><div className="post-top"><Link to={`/student/${item.owner.id}`} className="post-user"><span className="avatar">{initials(item.owner.name)}</span><span><strong>{item.owner.name}</strong><small>{studentInfo(item.owner)}</small></span></Link><span className="post-time">{timeAgo(item.created_at)}</span></div><Link to={`/market/${item.id}`} className="post-image">{item.image ? <img src={item.image} alt={item.title} loading="lazy" /> : <div className="image-fallback"><Gift size={50} /></div>}<span className="free-badge">{priceText(item.price)}</span></Link><div className="post-content"><div className="post-category">{item.category} · {item.condition}</div><Link to={`/market/${item.id}`}><h3>{item.title}</h3></Link><p>{item.description}</p><div className="post-footer"><span><MapPin size={16} /> {item.location}</span><Link to={`/market/${item.id}`}>Подробнее <ArrowRight size={17} /></Link></div></div></article>) : <Empty />}</div><aside className="feed-aside"><div className="aside-card"><div className="aside-icon telegram-aside-icon"><img src={telegramLogo} alt="" /></div><h3>Не пропускай новинки</h3><p>Telegram-бот CaspianHub сообщит, когда появится вещь из твоей категории.</p><Link to="/profile#telegram" className="btn btn-primary">Настроить уведомления <ArrowRight size={17} /></Link></div><div className="aside-tip"><span>✦ СОВЕТ CASPIANHUB</span><p>Нашёл интересную вещь? Свяжись с владельцем напрямую и договорись о встрече в университете.</p></div></aside></div></main>
}

function ListingDetail({ user }) {
  const { id } = useParams()
  const [item, setItem] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  useEffect(() => { api(`/listings/${id}`).then(setItem).catch(e => setError(e.message)) }, [id])
  async function changeStatus(status) { setBusy(true); try { setItem(await api(`/listings/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })) } catch (e) { setError(e.message) } finally { setBusy(false) } }
  async function remove() { if (!window.confirm('Удалить объявление?')) return; setBusy(true); try { await api(`/listings/${id}`, { method: 'DELETE' }); navigate(own ? '/profile' : '/market') } catch (e) { setError(e.message); setBusy(false) } }
  if (error && !item) return <main className="container simple-page"><Empty title="Вещь не найдена" text={error} /><Link className="btn btn-primary" to="/market">В маркет</Link></main>
  if (!item) return <main className="container simple-page loading">Загружаем карточку...</main>
  const contact = item.owner.contact.trim()
  const contactHref = contact.startsWith('@') ? `https://t.me/${contact.slice(1)}` : contact.startsWith('https://') ? contact : contact.includes('@') ? `mailto:${contact}` : `tel:${contact.replace(/[^+\d]/g, '')}`
  const own = user?.id === item.owner.id
  const canDelete = own || user?.is_admin
  return <main className="page detail-page"><div className="container"><Link to="/market" className="back-link"><ArrowLeft size={17} /> Вернуться в маркет</Link><div className="detail-grid"><div className="detail-photo">{item.image ? <img src={item.image} alt={item.title} /> : <div className="image-fallback"><Gift size={72} /></div>}<span className="free-badge">{priceText(item.price)}</span></div><div className="detail-info"><div className="detail-kicker"><span>{item.category}</span><span><Clock3 size={15} /> {dateText(item.created_at)}</span></div><h1>{item.title}</h1><strong className="listing-price">{priceText(item.price)}</strong><div className={`status-pill status-${item.status}`}><span /> {statusLabels[item.status]}</div>{item.status === "pending" && <div className="notice">Объявление задержано и пока не видно другим. {item.moderation_reason}</div>}<div className="detail-rule" /><h3>О вещи</h3><p className="detail-description">{item.description}</p><div className="detail-facts"><div><span>Состояние</span><strong>{item.condition}</strong></div><div><span>Где забрать</span><strong><MapPin size={16} /> {item.location}</strong></div></div><div className="owner-box"><span className="avatar avatar-large">{initials(item.owner.name)}</span><div><small>ВЛАДЕЛЕЦ ВЕЩИ</small><Link to={`/student/${item.owner.id}`}>{item.owner.name}</Link><span>{studentInfo(item.owner)}</span></div><ChevronRight size={19} /></div>{own ? <div className="owner-actions"><label>Статус объявления</label><select value={item.status} disabled={busy || item.status === "pending"} onChange={e => changeStatus(e.target.value)}>{item.status === "pending" && <option value="pending">На модерации</option>}<option value="available">Доступно</option><option value="reserved">Забронировано</option><option value="given">{item.price ? 'Продано' : 'Передано'}</option></select><button className="link-danger" disabled={busy} onClick={remove}>Удалить объявление</button></div> : item.status === 'available' && contact ? <a className="btn btn-primary contact-btn" href={contactHref} target={contactHref.startsWith('https://') ? '_blank' : undefined} rel="noreferrer">Связаться с владельцем <ArrowRight size={19} /></a> : <div className="notice">{item.status !== 'available' ? 'Вещь уже недоступна.' : 'Владелец ещё не указал контакт. Загляни позже.'}</div>}{canDelete && !own && <div className="owner-actions"><button className="link-danger" disabled={busy} onClick={remove}>Удалить объявление (администратор)</button></div>}{contact && <p className="contact-detail">Контакт: {contact}</p>}{error && <div className="notice error">{error}</div>}</div></div></div></main>
}

function Auth({ onAuth }) {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [mode, setMode] = useState('register')
  const [form, setForm] = useState({ name: '', email: '', password: '', education_level: '', study_group: '', contact: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const update = e => setForm({ ...form, [e.target.name]: e.target.value })
  async function submit(e) { e.preventDefault(); setBusy(true); setError(''); try { const data = await api(`/auth/${mode}`, { method: 'POST', body: JSON.stringify(mode === 'login' ? { email: form.email, password: form.password } : form) }); onAuth(data); navigate(searchParams.get('next')?.startsWith('/') ? searchParams.get('next') : '/profile') } catch (e) { setError(e.message) } finally { setBusy(false) } }
  return <main className="auth-page"><div className="container auth-layout"><div className="auth-story"><span className="section-label">ТВОЁ СООБЩЕСТВО. ТВОИ ВОЗМОЖНОСТИ.</span><h1>Твой аккаунт.<br /><em>Весь Caspian.</em></h1><p>События, маркет и возможности сообщества — в одном личном кабинете.</p><div className="auth-story-icon"><UserRound size={74} /></div></div><div className="auth-card"><div className="auth-tabs"><button className={mode === 'register' ? 'active' : ''} onClick={() => { setMode('register'); setError('') }}>Регистрация</button><button className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setError('') }}>Вход</button></div><div className="auth-card-body"><h2>{mode === 'register' ? 'Добро пожаловать!' : 'С возвращением!'}</h2><p>{mode === 'register' ? 'Создайте аккаунт и присоединяйтесь к сообществу Caspian.' : 'Войди в свой аккаунт, чтобы продолжить.'}</p><form onSubmit={submit} className="form-stack">{mode === 'register' && <><label>Твоё имя<input name="name" value={form.name} onChange={update} minLength={2} maxLength={100} required placeholder="Например, Алия Иванова" /></label><label>Где учишься<select name="education_level" value={form.education_level} onChange={update} required><option value="">Выбери вариант</option><option value="university">Университет</option><option value="college">Колледж</option></select></label><label>Группа <small>Необязательно</small><input name="study_group" value={form.study_group} onChange={update} maxLength={40} placeholder="Например, ИС-22-1" /></label></>}<label>Email<input type="email" name="email" value={form.email} onChange={update} required placeholder="student@example.com" /></label><label>Пароль<input type="password" name="password" value={form.password} onChange={update} minLength={8} required placeholder="Минимум 8 символов" /></label>{mode === 'register' && <label>Контакт для связи <small>Телефон, email или @username в Telegram</small><input name="contact" value={form.contact} onChange={update} maxLength={200} placeholder="@my_telegram" /></label>}{error && <div className="notice error">{error}</div>}<button className="btn btn-primary form-submit" disabled={busy}>{busy ? 'Подождите...' : mode === 'register' ? 'Создать аккаунт' : 'Войти'} <ArrowRight size={18} /></button></form><p className="auth-switch">{mode === 'register' ? 'Уже есть аккаунт?' : 'Ещё нет аккаунта?'} <button onClick={() => { setMode(mode === 'register' ? 'login' : 'register'); setError('') }}>{mode === 'register' ? 'Войти' : 'Зарегистрироваться'}</button></p></div></div></div></main>
}

function Create({ user }) {
  const navigate = useNavigate()
  const [form, setForm] = useState({ title: '', category: '', condition: '', location: '', description: '', image: '', price: '' })
  const [isPaid, setIsPaid] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (!user) return <main className="container simple-page"><Empty title="Сначала войди в аккаунт" text="Чтобы разместить вещь, создай профиль студента или войди." /><Link className="btn btn-primary" to="/auth?next=/market/new">Войти или зарегистрироваться</Link></main>
  if (!user.contact) return <main className="container simple-page"><Empty title="Добавь контакт для связи" text="Чтобы другие студенты могли забрать вещь, укажи Telegram, телефон или email в профиле." /><Link className="btn btn-primary" to="/profile">Открыть профиль</Link></main>
  const update = e => setForm({ ...form, [e.target.name]: e.target.value })
  function readImage(e) { const file = e.target.files?.[0]; if (!file) return; if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { setError('Выберите JPEG, PNG или WebP'); return } if (file.size > 2_000_000) { setError('Фото должно быть меньше 2 МБ'); return } const reader = new FileReader(); reader.onload = () => { setForm(current => ({ ...current, image: reader.result })); setError('') }; reader.readAsDataURL(file) }
  async function submit(e) { e.preventDefault(); setError(''); setBusy(true); try { const item = await api('/listings', { method: 'POST', body: JSON.stringify({ ...form, price: isPaid ? Number(form.price) : 0 }) }); navigate(`/market/${item.id}`) } catch (e) { setError(e.message) } finally { setBusy(false) } }
  return <main className="page create-page"><div className="page-hero"><div className="container"><span className="section-label">CASPIANHUB / МАРКЕТ</span><h1>Новое объявление<span className="accent-dot">.</span></h1><p>Разместите вещь на продажу или отдайте бесплатно.</p></div></div><div className="container create-layout"><form className="create-form" onSubmit={submit}><div className="form-section"><div className="form-section-title"><span>01</span><div><h2>Расскажи о вещи</h2><p>Чем подробнее описание, тем быстрее найдётся новый владелец.</p></div></div><div className="form-stack"><fieldset className="editor-choice-group"><legend>Как разместить вещь?</legend><label className={!isPaid ? 'selected' : ''}><input type="radio" name="listing_type" checked={!isPaid} onChange={() => setIsPaid(false)} /><span><strong>Отдать бесплатно</strong><small>Без оплаты</small></span></label><label className={isPaid ? 'selected' : ''}><input type="radio" name="listing_type" checked={isPaid} onChange={() => setIsPaid(true)} /><span><strong>Продать</strong><small>Указать цену в тенге</small></span></label></fieldset>{isPaid && <label>Цена, ₸<input name="price" type="number" min="1" max="100000000" step="1" value={form.price} onChange={update} required placeholder="Например, 5000" /></label>}<label>Название вещи<input name="title" value={form.title} onChange={update} minLength={3} maxLength={100} required placeholder="Например, учебник по маркетингу" /></label><div className="form-two"><label>Категория<select name="category" value={form.category} onChange={update} required><option value="">Выбери категорию</option>{categories.slice(1).map(x => <option key={x}>{x}</option>)}</select></label><label>Состояние<select name="condition" value={form.condition} onChange={update} required><option value="">Выбери состояние</option><option>Новое</option><option>Отличное состояние</option><option>Хорошее состояние</option><option>Есть следы использования</option></select></label></div><label>Описание<textarea name="description" value={form.description} onChange={update} minLength={10} maxLength={2000} required rows={5} placeholder="Расскажи о размере, особенностях, комплектации..." /></label><label>Где удобно передать<input name="location" value={form.location} onChange={update} minLength={2} maxLength={120} required placeholder="Например, главный корпус, библиотека" /></label></div></div><div className="form-section"><div className="form-section-title"><span>02</span><div><h2>Добавь фотографию</h2><p>Фото поможет заметить объявление в маркете.</p></div></div><label className="upload-box">{form.image ? <img src={form.image} alt="Предпросмотр вещи" /> : <><Camera size={33} /><strong>Нажми, чтобы загрузить фото</strong><span>JPEG, PNG или WebP · до 2 МБ</span></>}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={readImage} /></label>{form.image && <button type="button" className="text-button" onClick={() => setForm({ ...form, image: '' })}>Убрать фото</button>}</div>{error && <div className="notice error">{error}</div>}<button className="btn btn-primary publish-btn" disabled={busy}>{busy ? 'Публикуем...' : 'Опубликовать вещь'} <ArrowRight size={19} /></button></form><aside className="create-aside"><div className="aside-card"><div className="aside-icon"><Leaf size={26} /></div><h3>Договоритесь напрямую</h3><p>Укажите цену или выберите бесплатную передачу. Покупатель свяжется с вами через контакт в профиле; оплату и встречу вы согласуете самостоятельно.</p></div><div className="aside-tip"><span>✦ ХОРОШАЯ КАРТОЧКА</span><p>Сделай фото при дневном свете и честно опиши состояние вещи.</p></div></aside></div></main>
}

function Profile({ user, setUser, onLogout }) {
  const [profile, setProfile] = useState(null)
  const [telegram, setTelegram] = useState(null)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState(null)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const navigate = useNavigate()
  useEffect(() => { if (user) { api('/me').then(data => { setProfile(data); setForm({ name: data.name, education_level: data.education_level || "", study_group: data.study_group || "", contact: data.contact, bio: data.bio }) }).catch(e => setError(e.message)); api('/me/telegram').then(setTelegram).catch(() => { }) } }, [user])
  if (!user) return <main className="container simple-page"><Empty title="Твой профиль ждёт тебя" text="Войди или зарегистрируйся, чтобы видеть свои вещи и статистику." /><Link className="btn btn-primary" to="/auth?next=/profile">Войти или зарегистрироваться</Link></main>
  if (!profile) return <main className="container simple-page loading">Загружаем профиль...</main>
  async function saveProfile(e) { e.preventDefault(); setError(''); try { const data = await api('/me', { method: 'PATCH', body: JSON.stringify({ ...form, education_level: form.education_level || undefined }) }); setProfile({ ...profile, ...data }); setUser(data); setEditing(false); setSaved('Профиль обновлён') } catch (e) { setError(e.message) } }
  async function saveTelegram(next) { setError(''); try { const data = await api('/me/telegram', { method: 'PUT', body: JSON.stringify(next) }); setTelegram({ ...telegram, ...data }); setSaved('Настройки уведомлений сохранены') } catch (e) { setError(e.message) } }
  return <main className="page profile-page"><div className="profile-banner"><div className="container"><span className="section-label">МОЙ CASPIANHUB</span><h1>Личный кабинет<span className="accent-dot">.</span></h1><p>Ваши объявления, билеты и настройки — в одном месте.</p></div></div><div className="container profile-layout"><div className="profile-main"><div className="profile-events-link"><div><span className="section-label">CASPIANHUB / АФИША</span><h2>Планы после пар</h2></div><Link className="btn btn-primary btn-sm" to="/profile/tickets">Мои билеты <ArrowRight size={16} /></Link><Link className="text-link" to="/organizer">Организатору</Link></div><div className="profile-card"><div className="profile-top"><span className="avatar profile-avatar">{initials(profile.name)}</span><div><h2>{profile.name}</h2><p>{studentInfo(profile)}</p><span><MapPin size={14} /> Алматы, Казахстан</span></div><button className="icon-button" title="Редактировать профиль" onClick={() => setEditing(!editing)}><Edit3 size={19} /></button></div>{editing && <form className="form-stack profile-edit" onSubmit={saveProfile}><label>Имя<input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} minLength={2} required /></label><label>Где учишься<select value={form.education_level} onChange={e => setForm({ ...form, education_level: e.target.value })} required={!profile.is_admin}><option value="">Выбери вариант</option><option value="university">Университет</option><option value="college">Колледж</option></select></label><label>Группа<input value={form.study_group} onChange={e => setForm({ ...form, study_group: e.target.value })} maxLength={40} placeholder="Например, ИС-22-1" /></label><label>Контакт<input value={form.contact} onChange={e => setForm({ ...form, contact: e.target.value })} placeholder="@telegram или телефон" /></label><label>О себе<textarea value={form.bio} onChange={e => setForm({ ...form, bio: e.target.value })} rows={3} maxLength={400} /></label><button className="btn btn-primary">Сохранить</button></form>}{!editing && <div className="profile-contact"><span>Контакт для связи</span><strong>{profile.contact || 'Не указан — добавь контакт, чтобы тебе могли написать'}</strong>{profile.bio && <p>{profile.bio}</p>}</div>}</div><div className="stats-row"><div><span className="stat-icon blue"><Package size={21} /></span><strong>{profile.stats.published}</strong><small>Размещено</small></div><div><span className="stat-icon green"><Recycle size={22} /></span><strong>{profile.stats.given}</strong><small>Передано</small></div><div><span className="stat-icon yellow"><Heart size={21} /></span><strong>{profile.stats.active}</strong><small>Сейчас доступно</small></div></div><div className="profile-listings"><div className="subheading"><div><span className="section-label">МОИ ОБЪЯВЛЕНИЯ</span><h2>Мои объявления</h2></div><Link to="/market/new" className="btn btn-primary btn-sm"><Plus size={17} /> Добавить вещь</Link></div>{profile.listings.length ? <div className="my-items">{profile.listings.map(item => <Link to={`/market/${item.id}`} className="my-item" key={item.id}><div className="my-item-image">{item.image ? <img src={item.image} alt="" /> : <Gift size={24} />}</div><div><strong>{item.title}</strong><small>{priceText(item.price)} · {item.category} · {dateText(item.created_at)}</small></div><span className={`status-pill status-${item.status}`}>{statusLabels[item.status]}</span><ChevronRight size={17} /></Link>)}</div> : <Empty title="Здесь пока пусто" text="Размести первую вещь и помоги ей найти новый дом." />}</div></div><aside className="profile-aside"><div className="telegram-card" id="telegram"><span className="telegram-icon"><img src={telegramLogo} alt="" /></span><h3>Уведомления<br />в Telegram</h3><p>Узнавай первым о новых вещах в интересных тебе категориях.</p>{telegram?.connected ? <><div className="connected"><Check size={16} /> Бот подключён</div><div className="telegram-options">{categories.slice(1).map(category => <label key={category}><input type="checkbox" checked={telegram.categories.includes(category)} onChange={() => saveTelegram({ categories: telegram.categories.includes(category) ? telegram.categories.filter(x => x !== category) : [...telegram.categories, category], enabled: telegram.enabled })} /> {category}</label>)}</div><label className="notification-toggle"><input type="checkbox" checked={telegram.enabled} onChange={() => saveTelegram({ categories: telegram.categories, enabled: !telegram.enabled })} /> Уведомления включены</label></> : telegram?.bot_url ? <a className="btn btn-lime" href={telegram.bot_url} target="_blank" rel="noreferrer">Подключить бота <ArrowRight size={18} /></a> : <div className="telegram-unavailable">Бот появится после настройки BOT_TOKEN и BOT_USERNAME.</div>}</div><button className="logout-button" onClick={() => { onLogout(); navigate('/') }}><LogOut size={18} /> Выйти из аккаунта</button></aside></div>{error && <div className="container notice error">{error}</div>}{saved && <div className="toast" onClick={() => setSaved('')}><Check size={18} /> {saved} <X size={15} /></div>}</main>
}

function Student() {
  const { id } = useParams()
  const [student, setStudent] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api(`/users/${id}`).then(setStudent).catch(e => setError(e.message)) }, [id])
  if (error) return <main className="container simple-page"><Empty title="Студент не найден" text={error} /></main>
  if (!student) return <main className="container simple-page loading">Загружаем профиль...</main>
  return <main className="page student-page"><div className="container"><Link to="/market" className="back-link"><ArrowLeft size={17} /> В маркет</Link><div className="student-profile"><span className="avatar profile-avatar">{initials(student.name)}</span><div><span className="section-label">УЧАСТНИК CaspianHub</span><h1>{student.name}</h1><p>{studentInfo(student)}</p>{student.bio && <p>{student.bio}</p>}<div className="student-facts"><span><Package size={16} /> Размещено: {student.stats.published}</span><span><Recycle size={16} /> Передано: {student.stats.given}</span></div>{student.contact && <div className="student-contact">Контакт: <strong>{student.contact}</strong></div>}</div></div><div className="section-heading"><div><span className="section-label">ВЕЩИ СТУДЕНТА</span><h2>Объявления</h2></div></div>{student.listings.length ? <div className="item-grid">{student.listings.map(item => <ItemCard item={item} key={item.id} />)}</div> : <Empty />}</div></main>
}

function About() {
  return <main className="hub-about"><section className="container hub-welcome"><div><span className="section-label">О ПЛАТФОРМЕ CASPIANHUB</span><h1>Одно сообщество.<br /><em>Общие возможности.</em></h1><p>CaspianHub объединяет повседневную жизнь студентов: события, полезные находки и людей рядом.</p></div></section><section className="container hub-about-services"><Link to="/events"><CalendarDays size={30} /><span className="section-label">01 / АФИША</span><h2>Будьте частью событий</h2><p>Конференции, концерты, фестивали и встречи. Создавайте афиши, поддерживайте идеи и храните билеты в своём профиле.</p><ArrowUpRight /></Link><Link to="/market"><ShoppingBag size={30} /><span className="section-label">02 / МАРКЕТ</span><h2>Находите нужное у своих</h2><p>Продавайте, покупайте или отдавайте вещи бесплатно. Состояние, цена и контакт владельца — в каждой карточке.</p><ArrowUpRight /></Link><Link to="/profile"><UserRound size={30} /><span className="section-label">03 / МОЙ HUB</span><h2>Управляйте в одном месте</h2><p>Ваши объявления, билеты, информация профиля и уведомления. Один аккаунт для всех разделов.</p><ArrowUpRight /></Link></section><section className="container hub-community"><h2>Есть вопрос или идея?</h2><Link className="btn btn-primary" to="/support">Связаться с командой <ArrowRight size={18} /></Link></section></main>
}

function Publish() {
  return <main className="container publish-page"><span className="section-label">CASPIANHUB / СОЗДАТЬ</span><h1>Чем поделитесь с сообществом?</h1><div className="publish-options"><Link to="/events/new"><CalendarDays size={32} /><h2>Мероприятие</h2><p>Опубликуйте афишу, пригласите участников и управляйте регистрацией.</p><span>Создать событие <ArrowRight size={18} /></span></Link><Link to="/market/new"><ShoppingBag size={32} /><h2>Объявление в маркете</h2><p>Выставьте вещь на продажу или отдайте её бесплатно.</p><span>Разместить объявление <ArrowRight size={18} /></span></Link></div></main>
}

function LegacyMarketRedirect() { const location = useLocation(); return <Navigate replace to={`/market${location.search}`} /> }

function Support() {
  const [botUrl, setBotUrl] = useState('')
  const [loading, setLoading] = useState(true)
  useEffect(() => { api('/support').then(data => setBotUrl(data.bot_url || '')).catch(() => setBotUrl('')).finally(() => setLoading(false)) }, [])
  return <main className="page support-page"><div className="page-hero"><div className="container"><span className="section-label">ПОДДЕРЖКА CaspianHub</span><h1>Мы на связи в Telegram<span className="accent-dot">.</span></h1><p>Есть вопрос о работе сайта или объявлении? Напиши команде CaspianHub через нашего бота.</p></div></div><div className="container support-page-content"><div className="support-card"><span className="support-logo"><img src={telegramLogo} alt="Логотип Telegram" /></span><div><h2>Напиши в поддержку</h2><p>Открой бота, отправь свой вопрос одним сообщением и жди ответа в этом же чате.</p>{loading ? <span className="support-status">Проверяем доступность поддержки...</span> : botUrl ? <a className="btn btn-primary" href={botUrl} target="_blank" rel="noreferrer">Открыть поддержку в Telegram <ArrowRight size={18} /></a> : <div className="notice">Поддержка в Telegram пока не настроена. Попробуй позже.</div>}</div></div></div></main>
}

function AdminListings({ user }) {
  const [items, setItems] = useState([])
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  useEffect(() => {
    if (!user?.is_admin) return
    let active = true
    setLoading(true)
    api(`/listings?status=all&limit=100&offset=${offset}`).then(data => { if (active) { setItems(data); setError('') } }).catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [user?.is_admin, offset])
  if (!user?.is_admin) return <main className="container simple-page"><Empty title="Доступ только для администратора" /><Link className="btn btn-primary" to="/auth">Войти</Link></main>
  async function approve(item) {
    setBusyId(item.id)
    setError("")
    try {
      const approved = await api(`/admin/listings/${item.id}/approve`, { method: "POST" })
      setItems(current => current.map(entry => entry.id === item.id ? approved : entry))
    } catch (e) { setError(e.message) } finally { setBusyId(null) }
  }
  async function remove(item) {
    if (!window.confirm(`Удалить объявление «${item.title}»?`)) return
    setBusyId(item.id)
    setError('')
    try {
      await api(`/listings/${item.id}`, { method: 'DELETE' })
      setItems(current => current.filter(entry => entry.id !== item.id))
    } catch (e) { setError(e.message) } finally { setBusyId(null) }
  }
  return <main className="page"><div className="page-hero"><div className="container"><span className="section-label">КОМАНДА CASPIANHUB</span><h1>Управление объявлениями<span className="accent-dot">.</span></h1><p>Все объявления сообщества, включая забронированные и переданные.</p></div></div><div className="container admin-listings">{error && <div className="notice error">{error}</div>}{loading ? <div className="loading">Загружаем объявления...</div> : items.length ? <div className="my-items">{items.map(item => <div className="my-item admin-item" key={item.id}><div className="my-item-image">{item.image ? <img src={item.image} alt="" /> : <Gift size={24} />}</div><div><Link to={`/market/${item.id}`}><strong>{item.title}</strong></Link><small>{item.owner.name} · {item.category} · {dateText(item.created_at)}</small></div><span className={`status-pill status-${item.status}`}>{statusLabels[item.status]}</span>{item.status === "pending" && <button className="btn btn-primary btn-sm" disabled={busyId === item.id} onClick={() => approve(item)}>Опубликовать</button>}<button className="link-danger" disabled={busyId === item.id} onClick={() => remove(item)}>Удалить</button></div>)}</div> : <Empty title="Объявлений пока нет" />}{!loading && <div className="admin-pagination"><button className="btn btn-primary btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>Назад</button><span>Страница {Math.floor(offset / 100) + 1}</span><button className="btn btn-primary btn-sm" disabled={items.length < 100} onClick={() => setOffset(offset + 100)}>Далее</button></div>}</div></main>
}

export default function App() {
  const [user, setUser] = useState(() => { try { return JSON.parse(localStorage.getItem('caspianhub_user') || 'null') } catch { return null } })
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme === 'light' ? 'light' : 'dark')
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#1d1713' : '#ffffff')
    try { localStorage.setItem('caspianhub_theme', theme) } catch { /* Theme still works when storage is unavailable. */ }
  }, [theme])
  useEffect(() => { if (localStorage.getItem('caspianhub_token')) api('/me').then(data => { localStorage.setItem('caspianhub_user', JSON.stringify(data)); setUser(data) }).catch(() => {}) }, [])
  function onAuth(data) { localStorage.setItem('caspianhub_token', data.token); localStorage.setItem('caspianhub_user', JSON.stringify(data.user)); setUser(data.user) }
  function updateUser(data) { localStorage.setItem('caspianhub_user', JSON.stringify(data)); setUser(data) }
  function onLogout() { localStorage.removeItem('caspianhub_token'); localStorage.removeItem('caspianhub_user'); setUser(null) }
  return <><a className="skip-link" href="#page-content">К содержимому</a><Header user={user} theme={theme} onThemeToggle={() => setTheme(current => current === 'dark' ? 'light' : 'dark')} /><div id="page-content" tabIndex={-1}><Routes><Route path="/publish" element={<Publish />} /><Route path="/catalog" element={<LegacyMarketRedirect />} /><Route path="/create" element={<Navigate replace to="/market/new" />} /><Route path="/listing/:id" element={<ListingDetail user={user} />} /><Route path="/events" element={<Events />} /><Route path="/events/new" element={<CreateEvent user={user} />} /><Route path="/events/:id" element={<EventDetail user={user} />} /><Route path="/profile/tickets" element={<MyTickets user={user} />} /><Route path="/organizer" element={<Organizer user={user} />} /><Route path="/" element={<HubHome />} /><Route path="/market" element={<Catalog />} /><Route path="/feed" element={<Feed />} /><Route path="/market/:id" element={<ListingDetail user={user} />} /><Route path="/auth" element={<Auth onAuth={onAuth} />} /><Route path="/market/new" element={<Create user={user} />} /><Route path="/profile" element={<Profile user={user} setUser={updateUser} onLogout={onLogout} />} /><Route path="/admin" element={<AdminListings user={user} />} /><Route path="/student/:id" element={<Student />} /><Route path="/about" element={<About />} /><Route path="/support" element={<Support />} /><Route path="*" element={<main className="container simple-page"><Empty title="Страница не найдена" text="Возможно, ссылка устарела." /><Link className="btn btn-primary" to="/">На главную</Link></main>} /></Routes></div><Footer /></>
}
