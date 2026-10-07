import { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, Route, Routes, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Bell, BookOpen, Check, ChevronRight, Clock3, Heart, Laptop, Leaf, MapPin, Menu, Plus, Search, Shirt, SlidersHorizontal, Sparkles, Send, UserRound, X, Home as HomeIcon, Package, LogOut, Edit3, ExternalLink, Camera, Gift, Recycle } from 'lucide-react'
import { api, categories } from './api'
import { Lottie } from 'lottie-react'
import curuAnimation from './animations/curu.json'
import curuLogo from './logos/logo.png'

const categoryIcons = { 'Все': Sparkles, 'Одежда': Shirt, 'Гаджеты': Laptop, 'Книги': BookOpen, 'Для учёбы': Edit3, 'Для дома': HomeIcon, 'Другое': Package }
const statusLabels = { available: 'Доступно', reserved: 'Забронировано', given: 'Передано' }
const dateText = value => new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
const timeAgo = value => {
  const hours = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 3600000))
  if (hours < 1) return 'Только что'
  if (hours < 24) return `${hours} ч назад`
  const days = Math.floor(hours / 24)
  return days === 1 ? 'Вчера' : `${days} дн назад`
}
const initials = name => (name || 'C').split(' ').map(x => x[0]).slice(0, 2).join('').toUpperCase()
const studentInfo = person => [person.education_level === 'college' ? 'Колледж' : person.education_level === 'university' ? 'Университет' : 'Участник CURU', person.study_group ? `группа ${person.study_group}` : ''].filter(Boolean).join(' · ')

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
  return <Link to="/" className={`brand ${light ? 'brand-light' : ''}`} aria-label="CURU — главная">
    <img className="brand-logo" src={curuLogo} alt="CURU" />
  </Link>
}

function Header({ user, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const navigate = useNavigate()
  const close = () => setMenuOpen(false)
  return <header className="site-header">
    <div className="container header-inner">
      <Brand />
      <nav className={`main-nav ${menuOpen ? 'open' : ''}`} aria-label="Главное меню">
        <NavLink onClick={close} end to="/">Главная</NavLink>
        <NavLink onClick={close} to="/catalog">Каталог</NavLink>
        <NavLink onClick={close} to="/feed">Лента</NavLink>
        <NavLink onClick={close} to="/about">О проекте</NavLink>
        {user?.is_admin && <NavLink onClick={close} to="/admin">Админ</NavLink>}
      </nav>
      <div className="header-actions">
        <button className="btn btn-primary btn-sm header-add" onClick={() => navigate(user ? '/create' : '/auth?next=/create')}><Plus size={18} /> Разместить вещь</button>
        <Link className="header-account" to={user ? '/profile' : '/auth'} title={user ? 'Мой профиль' : 'Войти'}><UserRound size={19} /><span>{user ? user.name.split(' ')[0] : 'Войти'}</span></Link>
        <button className="mobile-menu" aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X /> : <Menu />}</button>
      </div>
    </div>
  </header>
}

function Footer() {
  return <footer className="footer"><div className="container footer-grid">
    <div><Brand light /><span className="footer-tagline">ЭКОШЕРИНГ СООБЩЕСТВО CASPIAN UNIVERSITY</span><p>Вторая жизнь вещей начинается здесь.<br />Сообщество студентов Caspian University.</p></div>
    <div><b>Платформа</b><Link to="/catalog">Каталог вещей</Link><Link to="/feed">Лента новинок</Link><Link to="/create">Разместить вещь</Link></div>
    <div><b>Информация</b><Link to="/about">О проекте</Link><a href="https://cu.edu.kz/" target="_blank" rel="noreferrer">Caspian University <ExternalLink size={12} /></a></div>
    <div className="footer-note"><span>♻️</span><p>Делимся вещами.<br />Заботимся о планете.</p></div>
  </div><div className="container footer-bottom"><span>© 2026 CURU. Сделано студентами для студентов.</span><span>Алматы, Казахстан</span></div></footer>
}

function ItemCard({ item, compact = false }) {
  return <Link to={`/listing/${item.id}`} className={`item-card ${compact ? 'compact' : ''}`}>
    <div className="item-photo">{item.image ? <img src={item.image} alt={item.title} loading="lazy" /> : <div className="image-fallback"><Gift size={42} /></div>}<span className="free-badge">БЕСПЛАТНО</span></div>
    <div className="item-body"><div className="item-kicker"><span>{item.category}</span><span>{timeAgo(item.created_at)}</span></div><h3>{item.title}</h3><div className="item-meta"><MapPin size={15} /> {item.location}</div></div>
  </Link>
}

function Empty({ title = 'Пока ничего нет', text = 'Попробуйте другую категорию или загляните позже.' }) {
  return <div className="empty"><span><Package size={30} /></span><h3>{title}</h3><p>{text}</p></div>
}

function Home() {
  const { items, loading } = useItems('?limit=6')
  return <>
    <section className="hero"><div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" /><div className="container hero-grid">
      <div className="hero-copy"><h1>Вещам —<br /><em>новую жизнь.</em><br />Студентам —<br />новые возможности.</h1><p>Отдавай то, что больше не нужно, и находи полезное у своих. Бесплатно, просто и с заботой о планете.</p><div className="hero-buttons"><Link to="/catalog" className="btn btn-lime">Найти вещь <ArrowRight size={19} /></Link><Link to="/create" className="btn btn-outline-light">Отдать вещь <Plus size={18} /></Link></div></div>
        <div className="hero-visual" role="img" aria-label="Анимация CURU о передаче вещей"><Lottie src={curuAnimation} loop autoplay className="hero-animation" /></div>
      </div><div className="hero-bottom-line" /></section>
    <section className="steps-strip"><div className="container steps-inner"><div><span className="step-icon"><Search size={22} /></span><p><strong>Найди</strong><br />то, что нужно</p></div><ChevronRight className="step-chevron" /><div><span className="step-icon"><UserRound size={22} /></span><p><strong>Свяжись</strong><br />со студентом</p></div><ChevronRight className="step-chevron" /><div><span className="step-icon"><Heart size={22} /></span><p><strong>Забери</strong><br />и дай вещи новую жизнь</p></div></div></section>
    <section className="section categories-section"><div className="container"><div className="section-heading"><div><span className="section-label">НАЙДИ СВОЁ</span><h2>Что ищем сегодня?</h2><p>Выбирай категорию и находи нужные вещи рядом с тобой.</p></div><Link className="text-link" to="/catalog">Весь каталог <ArrowRight size={18} /></Link></div><div className="category-grid">{categories.slice(1).map((name, i) => { const Icon = categoryIcons[name]; return <Link to={`/catalog?category=${encodeURIComponent(name)}`} className={`category-tile category-${i}`} key={name}><span className="category-icon"><Icon size={26} strokeWidth={1.8} /></span><strong>{name}</strong><ArrowRight size={18} /></Link> })}</div></div></section>
    <section className="section latest-section"><div className="container"><div className="section-heading"><div><span className="section-label">ТОЛЬКО ЧТО ДОБАВИЛИ</span><h2>Новые вещи в CURU <span className="heading-spark">✳</span></h2><p>Возможно, именно здесь тебя ждёт что-то особенное.</p></div><Link className="text-link" to="/feed">Смотреть ленту <ArrowRight size={18} /></Link></div>{loading ? <div className="loading">Загружаем вещи...</div> : items.length ? <div className="item-grid">{items.slice(0, 4).map(item => <ItemCard key={item.id} item={item} />)}</div> : <Empty />}</div></section>
    <section className="container"><div className="mission-banner"><div className="mission-art"><div className="mission-circle"><Recycle size={74} strokeWidth={1.3} /></div><span>✳</span><span>✦</span></div><div><span className="section-label">МАЛЕНЬКИЕ ДЕЙСТВИЯ — БОЛЬШИЕ ПЕРЕМЕНЫ</span><h2>Не выбрасывай.<br /><em>Передавай дальше.</em></h2><p>Каждая вещь, которая нашла нового владельца, — это меньше отходов и больше возможностей для кого-то рядом.</p><Link to="/about" className="btn btn-dark">Узнать о проекте <ArrowRight size={18} /></Link></div></div></section>
    <section className="section join-section"><div className="container join-inner"><div><span className="section-label">НАЧНИ СЕГОДНЯ</span><h2>У тебя есть вещь,<br />которая пригодится другому?</h2><p>Пара минут — и она может стать чьей-то любимой.</p></div><Link to="/create" className="btn btn-lime">Разместить бесплатно <Plus size={19} /></Link></div></section>
  </>
}

function Catalog() {
  const [searchParams, setSearchParams] = useSearchParams()
  const category = searchParams.get('category') || 'Все'
  const q = searchParams.get('q') || ''
  const [input, setInput] = useState(q)
  useEffect(() => setInput(q), [q])
  const params = useMemo(() => `?${new URLSearchParams({ ...(category !== 'Все' ? { category } : {}), ...(q ? { q } : {}), limit: '100' })}`, [category, q])
  const { items, loading, error } = useItems(params)
  const setCategory = value => setSearchParams({ ...(value !== 'Все' ? { category: value } : {}), ...(q ? { q } : {}) })
  const submit = e => { e.preventDefault(); setSearchParams({ ...(category !== 'Все' ? { category } : {}), ...(input.trim() ? { q: input.trim() } : {}) }) }
  return <main className="page"><div className="page-hero catalog-hero"><div className="container"><span className="section-label">ПОДЕЛИСЬ · НАЙДИ · ПОВТОРИ</span><h1>Каталог вещей<span className="accent-dot">.</span></h1><p>Полезные находки от студентов Caspian University — бесплатно.</p></div></div><div className="container catalog-content"><div className="catalog-toolbar"><form className="search-box" onSubmit={submit}><Search size={20} /><input value={input} onChange={e => setInput(e.target.value)} placeholder="Что ищешь? Например, учебник или рюкзак" aria-label="Поиск вещей" /><button type="submit">Найти <ArrowRight size={17} /></button></form><span className="catalog-count">{loading ? 'Загрузка...' : `${items.length} ${items.length === 1 ? 'вещь' : 'вещей'}`}</span></div><div className="filter-row"><span className="filter-label"><SlidersHorizontal size={17} /> Категории</span><div className="filter-chips">{categories.map(name => <button className={`chip ${category === name ? 'active' : ''}`} onClick={() => setCategory(name)} key={name}>{name}</button>)}</div></div>{error ? <div className="notice error">{error}</div> : loading ? <div className="loading">Загружаем каталог...</div> : items.length ? <div className="item-grid catalog-grid">{items.map(item => <ItemCard item={item} key={item.id} />)}</div> : <Empty title="Ничего не нашлось" text="Попробуй другой запрос или категорию — новые вещи появляются постоянно." />}</div></main>
}

function Feed() {
  const { items, loading, error } = useItems('?limit=100')
  return <main className="page feed-page"><div className="page-hero feed-hero"><div className="container"><span className="section-label">ЛЕНТА СООБЩЕСТВА</span><h1>Что нового в CURU<span className="accent-dot">.</span></h1><p>Листай, вдохновляйся и находи вещи с историей.</p></div></div><div className="container feed-layout"><div className="feed-main"><div className="feed-heading"><div className="live-dot" /><h2>Свежие публикации</h2><span>Сначала новые</span></div>{error ? <div className="notice error">{error}</div> : loading ? <div className="loading">Загружаем ленту...</div> : items.length ? items.map(item => <article className="feed-post" key={item.id}><div className="post-top"><Link to={`/student/${item.owner.id}`} className="post-user"><span className="avatar">{initials(item.owner.name)}</span><span><strong>{item.owner.name}</strong><small>{studentInfo(item.owner)}</small></span></Link><span className="post-time">{timeAgo(item.created_at)}</span></div><Link to={`/listing/${item.id}`} className="post-image">{item.image ? <img src={item.image} alt={item.title} loading="lazy" /> : <div className="image-fallback"><Gift size={50} /></div>}<span className="free-badge">БЕСПЛАТНО</span></Link><div className="post-content"><div className="post-category">{item.category} · {item.condition}</div><Link to={`/listing/${item.id}`}><h3>{item.title}</h3></Link><p>{item.description}</p><div className="post-footer"><span><MapPin size={16} /> {item.location}</span><Link to={`/listing/${item.id}`}>Подробнее <ArrowRight size={17} /></Link></div></div></article>) : <Empty />}</div><aside className="feed-aside"><div className="aside-card"><div className="aside-icon"><Bell size={25} /></div><h3>Не пропускай новинки</h3><p>Telegram-бот CURU сообщит, когда появится вещь из твоей категории.</p><Link to="/profile#telegram" className="btn btn-primary">Настроить уведомления <ArrowRight size={17} /></Link></div><div className="aside-tip"><span>✦ СОВЕТ CURU</span><p>Нашёл интересную вещь? Свяжись с владельцем напрямую и договорись о встрече в университете.</p></div></aside></div></main>
}

function ListingDetail({ user }) {
  const { id } = useParams()
  const [item, setItem] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  useEffect(() => { api(`/listings/${id}`).then(setItem).catch(e => setError(e.message)) }, [id])
  async function changeStatus(status) { setBusy(true); try { setItem(await api(`/listings/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })) } catch (e) { setError(e.message) } finally { setBusy(false) } }
  async function remove() { if (!window.confirm('Удалить объявление?')) return; setBusy(true); try { await api(`/listings/${id}`, { method: 'DELETE' }); navigate(own ? '/profile' : '/catalog') } catch (e) { setError(e.message); setBusy(false) } }
  if (error && !item) return <main className="container simple-page"><Empty title="Вещь не найдена" text={error} /><Link className="btn btn-primary" to="/catalog">К каталогу</Link></main>
  if (!item) return <main className="container simple-page loading">Загружаем карточку...</main>
  const contact = item.owner.contact.trim()
  const contactHref = contact.startsWith('@') ? `https://t.me/${contact.slice(1)}` : contact.startsWith('https://') ? contact : contact.includes('@') ? `mailto:${contact}` : `tel:${contact.replace(/[^+\d]/g, '')}`
  const own = user?.id === item.owner.id
  const canDelete = own || user?.is_admin
  return <main className="page detail-page"><div className="container"><Link to="/catalog" className="back-link"><ArrowLeft size={17} /> Вернуться в каталог</Link><div className="detail-grid"><div className="detail-photo">{item.image ? <img src={item.image} alt={item.title} /> : <div className="image-fallback"><Gift size={72} /></div>}<span className="free-badge">БЕСПЛАТНО</span></div><div className="detail-info"><div className="detail-kicker"><span>{item.category}</span><span><Clock3 size={15} /> {dateText(item.created_at)}</span></div><h1>{item.title}</h1><div className={`status-pill status-${item.status}`}><span /> {statusLabels[item.status]}</div><div className="detail-rule" /><h3>О вещи</h3><p className="detail-description">{item.description}</p><div className="detail-facts"><div><span>Состояние</span><strong>{item.condition}</strong></div><div><span>Где забрать</span><strong><MapPin size={16} /> {item.location}</strong></div></div><div className="owner-box"><span className="avatar avatar-large">{initials(item.owner.name)}</span><div><small>ВЛАДЕЛЕЦ ВЕЩИ</small><Link to={`/student/${item.owner.id}`}>{item.owner.name}</Link><span>{studentInfo(item.owner)}</span></div><ChevronRight size={19} /></div>{own ? <div className="owner-actions"><label>Статус объявления</label><select value={item.status} disabled={busy} onChange={e => changeStatus(e.target.value)}><option value="available">Доступно</option><option value="reserved">Забронировано</option><option value="given">Передано</option></select><button className="link-danger" disabled={busy} onClick={remove}>Удалить объявление</button></div> : item.status === 'available' && contact ? <a className="btn btn-primary contact-btn" href={contactHref} target={contactHref.startsWith('https://') ? '_blank' : undefined} rel="noreferrer">Связаться с владельцем <ArrowRight size={19} /></a> : <div className="notice">{item.status !== 'available' ? 'Вещь уже недоступна.' : 'Владелец ещё не указал контакт. Загляни позже.'}</div>}{canDelete && !own && <div className="owner-actions"><button className="link-danger" disabled={busy} onClick={remove}>Удалить объявление (администратор)</button></div>}{contact && <p className="contact-detail">Контакт: {contact}</p>}{error && <div className="notice error">{error}</div>}</div></div></div></main>
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
  return <main className="auth-page"><div className="container auth-layout"><div className="auth-story"><span className="section-label">ТВОЁ СООБЩЕСТВО. ТВОИ ВОЗМОЖНОСТИ.</span><h1>Присоединяйся<br />к доброму<br /><em>круговороту.</em></h1><p>Находи вещи, которые пригодятся, и передавай свои другим студентам университета и колледжа.</p><div className="auth-story-icon"><Recycle size={74} /></div></div><div className="auth-card"><div className="auth-tabs"><button className={mode === 'register' ? 'active' : ''} onClick={() => { setMode('register'); setError('') }}>Регистрация</button><button className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setError('') }}>Вход</button></div><div className="auth-card-body"><h2>{mode === 'register' ? 'Привет, будущий CURU!' : 'С возвращением!'}</h2><p>{mode === 'register' ? 'Создай аккаунт, чтобы делиться вещами и находить новое.' : 'Войди в свой аккаунт, чтобы продолжить.'}</p><form onSubmit={submit} className="form-stack">{mode === 'register' && <><label>Твоё имя<input name="name" value={form.name} onChange={update} minLength={2} maxLength={100} required placeholder="Например, Алия Иванова" /></label><label>Где учишься<select name="education_level" value={form.education_level} onChange={update} required><option value="">Выбери вариант</option><option value="university">Университет</option><option value="college">Колледж</option></select></label><label>Группа <small>Необязательно</small><input name="study_group" value={form.study_group} onChange={update} maxLength={40} placeholder="Например, ИС-22-1" /></label></>}<label>Email<input type="email" name="email" value={form.email} onChange={update} required placeholder="student@example.com" /></label><label>Пароль<input type="password" name="password" value={form.password} onChange={update} minLength={8} required placeholder="Минимум 8 символов" /></label>{mode === 'register' && <label>Контакт для связи <small>Телефон, email или @username в Telegram</small><input name="contact" value={form.contact} onChange={update} maxLength={200} placeholder="@my_telegram" /></label>}{error && <div className="notice error">{error}</div>}<button className="btn btn-primary form-submit" disabled={busy}>{busy ? 'Подождите...' : mode === 'register' ? 'Создать аккаунт' : 'Войти'} <ArrowRight size={18} /></button></form><p className="auth-switch">{mode === 'register' ? 'Уже есть аккаунт?' : 'Ещё нет аккаунта?'} <button onClick={() => { setMode(mode === 'register' ? 'login' : 'register'); setError('') }}>{mode === 'register' ? 'Войти' : 'Зарегистрироваться'}</button></p></div></div></div></main>
}

function Create({ user }) {
  const navigate = useNavigate()
  const [form, setForm] = useState({ title: '', category: '', condition: '', location: '', description: '', image: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (!user) return <main className="container simple-page"><Empty title="Сначала войди в аккаунт" text="Чтобы разместить вещь, создай профиль студента или войди." /><Link className="btn btn-primary" to="/auth?next=/create">Войти или зарегистрироваться</Link></main>
  if (!user.contact) return <main className="container simple-page"><Empty title="Добавь контакт для связи" text="Чтобы другие студенты могли забрать вещь, укажи Telegram, телефон или email в профиле." /><Link className="btn btn-primary" to="/profile">Открыть профиль</Link></main>
  const update = e => setForm({ ...form, [e.target.name]: e.target.value })
  function readImage(e) { const file = e.target.files?.[0]; if (!file) return; if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { setError('Выберите JPEG, PNG или WebP'); return } if (file.size > 2_000_000) { setError('Фото должно быть меньше 2 МБ'); return } const reader = new FileReader(); reader.onload = () => { setForm(current => ({ ...current, image: reader.result })); setError('') }; reader.readAsDataURL(file) }
  async function submit(e) { e.preventDefault(); setError(''); setBusy(true); try { const item = await api('/listings', { method: 'POST', body: JSON.stringify(form) }); navigate(`/listing/${item.id}`) } catch (e) { setError(e.message) } finally { setBusy(false) } }
  return <main className="page create-page"><div className="page-hero"><div className="container"><span className="section-label">ПОДЕЛИТЬСЯ ПРОСТО</span><h1>Передай вещь дальше<span className="accent-dot">.</span></h1><p>Заполни карточку, и твоя вещь найдёт нового владельца.</p></div></div><div className="container create-layout"><form className="create-form" onSubmit={submit}><div className="form-section"><div className="form-section-title"><span>01</span><div><h2>Расскажи о вещи</h2><p>Чем подробнее описание, тем быстрее найдётся новый владелец.</p></div></div><div className="form-stack"><label>Название вещи<input name="title" value={form.title} onChange={update} minLength={3} maxLength={100} required placeholder="Например, учебник по маркетингу" /></label><div className="form-two"><label>Категория<select name="category" value={form.category} onChange={update} required><option value="">Выбери категорию</option>{categories.slice(1).map(x => <option key={x}>{x}</option>)}</select></label><label>Состояние<select name="condition" value={form.condition} onChange={update} required><option value="">Выбери состояние</option><option>Новое</option><option>Отличное состояние</option><option>Хорошее состояние</option><option>Есть следы использования</option></select></label></div><label>Описание<textarea name="description" value={form.description} onChange={update} minLength={10} maxLength={2000} required rows={5} placeholder="Расскажи о размере, особенностях, комплектации..." /></label><label>Где удобно передать<input name="location" value={form.location} onChange={update} minLength={2} maxLength={120} required placeholder="Например, главный корпус, библиотека" /></label></div></div><div className="form-section"><div className="form-section-title"><span>02</span><div><h2>Добавь фотографию</h2><p>Фото поможет заметить твою вещь в каталоге.</p></div></div><label className="upload-box">{form.image ? <img src={form.image} alt="Предпросмотр вещи" /> : <><Camera size={33} /><strong>Нажми, чтобы загрузить фото</strong><span>JPEG, PNG или WebP · до 2 МБ</span></>}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={readImage} /></label>{form.image && <button type="button" className="text-button" onClick={() => setForm({ ...form, image: '' })}>Убрать фото</button>}</div>{error && <div className="notice error">{error}</div>}<button className="btn btn-primary publish-btn" disabled={busy}>{busy ? 'Публикуем...' : 'Опубликовать вещь'} <ArrowRight size={19} /></button></form><aside className="create-aside"><div className="aside-card"><div className="aside-icon"><Leaf size={26} /></div><h3>Дарить легко</h3><p>В CURU все вещи передаются бесплатно. Укажи удобное место встречи и дождись сообщения от другого студента.</p></div><div className="aside-tip"><span>✦ ХОРОШАЯ КАРТОЧКА</span><p>Сделай фото при дневном свете и честно опиши состояние вещи.</p></div></aside></div></main>
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
  return <main className="page profile-page"><div className="profile-banner"><div className="container"><span className="section-label">МОЙ CURU</span><h1>Личный кабинет<span className="accent-dot">.</span></h1><p>Твои вещи, твой вклад, твоя история.</p></div></div><div className="container profile-layout"><div className="profile-main"><div className="profile-card"><div className="profile-top"><span className="avatar profile-avatar">{initials(profile.name)}</span><div><h2>{profile.name}</h2><p>{studentInfo(profile)}</p><span><MapPin size={14} /> Алматы, Казахстан</span></div><button className="icon-button" title="Редактировать профиль" onClick={() => setEditing(!editing)}><Edit3 size={19} /></button></div>{editing && <form className="form-stack profile-edit" onSubmit={saveProfile}><label>Имя<input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} minLength={2} required /></label><label>Где учишься<select value={form.education_level} onChange={e => setForm({ ...form, education_level: e.target.value })} required={!profile.is_admin}><option value="">Выбери вариант</option><option value="university">Университет</option><option value="college">Колледж</option></select></label><label>Группа<input value={form.study_group} onChange={e => setForm({ ...form, study_group: e.target.value })} maxLength={40} placeholder="Например, ИС-22-1" /></label><label>Контакт<input value={form.contact} onChange={e => setForm({ ...form, contact: e.target.value })} placeholder="@telegram или телефон" /></label><label>О себе<textarea value={form.bio} onChange={e => setForm({ ...form, bio: e.target.value })} rows={3} maxLength={400} /></label><button className="btn btn-primary">Сохранить</button></form>}{!editing && <div className="profile-contact"><span>Контакт для связи</span><strong>{profile.contact || 'Не указан — добавь контакт, чтобы тебе могли написать'}</strong>{profile.bio && <p>{profile.bio}</p>}</div>}</div><div className="stats-row"><div><span className="stat-icon blue"><Package size={21} /></span><strong>{profile.stats.published}</strong><small>Размещено</small></div><div><span className="stat-icon green"><Recycle size={22} /></span><strong>{profile.stats.given}</strong><small>Передано</small></div><div><span className="stat-icon yellow"><Heart size={21} /></span><strong>{profile.stats.active}</strong><small>Сейчас доступно</small></div></div><div className="profile-listings"><div className="subheading"><div><span className="section-label">МОИ ОБЪЯВЛЕНИЯ</span><h2>Мои вещи</h2></div><Link to="/create" className="btn btn-primary btn-sm"><Plus size={17} /> Добавить вещь</Link></div>{profile.listings.length ? <div className="my-items">{profile.listings.map(item => <Link to={`/listing/${item.id}`} className="my-item" key={item.id}><div className="my-item-image">{item.image ? <img src={item.image} alt="" /> : <Gift size={24} />}</div><div><strong>{item.title}</strong><small>{item.category} · {dateText(item.created_at)}</small></div><span className={`status-pill status-${item.status}`}>{statusLabels[item.status]}</span><ChevronRight size={17} /></Link>)}</div> : <Empty title="Здесь пока пусто" text="Размести первую вещь и помоги ей найти новый дом." />}</div></div><aside className="profile-aside"><div className="telegram-card" id="telegram"><span className="telegram-icon"><Send size={28} /></span><h3>Уведомления<br />в Telegram</h3><p>Узнавай первым о новых вещах в интересных тебе категориях.</p>{telegram?.connected ? <><div className="connected"><Check size={16} /> Бот подключён</div><div className="telegram-options">{categories.slice(1).map(category => <label key={category}><input type="checkbox" checked={telegram.categories.includes(category)} onChange={() => saveTelegram({ categories: telegram.categories.includes(category) ? telegram.categories.filter(x => x !== category) : [...telegram.categories, category], enabled: telegram.enabled })} /> {category}</label>)}</div><label className="notification-toggle"><input type="checkbox" checked={telegram.enabled} onChange={() => saveTelegram({ categories: telegram.categories, enabled: !telegram.enabled })} /> Уведомления включены</label></> : telegram?.bot_url ? <a className="btn btn-lime" href={telegram.bot_url} target="_blank" rel="noreferrer">Подключить бота <ArrowRight size={18} /></a> : <div className="telegram-unavailable">Бот появится после настройки BOT_TOKEN и BOT_USERNAME.</div>}</div><button className="logout-button" onClick={() => { onLogout(); navigate('/') }}><LogOut size={18} /> Выйти из аккаунта</button></aside></div>{error && <div className="container notice error">{error}</div>}{saved && <div className="toast" onClick={() => setSaved('')}><Check size={18} /> {saved} <X size={15} /></div>}</main>
}

function Student() {
  const { id } = useParams()
  const [student, setStudent] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api(`/users/${id}`).then(setStudent).catch(e => setError(e.message)) }, [id])
  if (error) return <main className="container simple-page"><Empty title="Студент не найден" text={error} /></main>
  if (!student) return <main className="container simple-page loading">Загружаем профиль...</main>
  return <main className="page student-page"><div className="container"><Link to="/catalog" className="back-link"><ArrowLeft size={17} /> К каталогу</Link><div className="student-profile"><span className="avatar profile-avatar">{initials(student.name)}</span><div><span className="section-label">УЧАСТНИК CURU</span><h1>{student.name}</h1><p>{studentInfo(student)}</p>{student.bio && <p>{student.bio}</p>}<div className="student-facts"><span><Package size={16} /> Размещено: {student.stats.published}</span><span><Recycle size={16} /> Передано: {student.stats.given}</span></div>{student.contact && <div className="student-contact">Контакт: <strong>{student.contact}</strong></div>}</div></div><div className="section-heading"><div><span className="section-label">ВЕЩИ СТУДЕНТА</span><h2>Объявления</h2></div></div>{student.listings.length ? <div className="item-grid">{student.listings.map(item => <ItemCard item={item} key={item.id} />)}</div> : <Empty />}</div></main>
}

function About() {
  return <main className="page about-page"><section className="about-hero"><div className="container"><span className="section-label">CCU RE-USE</span><h1>Меняем вещи.<br /><em>Меняем привычки.</em></h1><p>CURU — пространство, где студенты Caspian University делятся тем, что им больше не нужно, и находят полезное друг у друга.</p><Link to="/catalog" className="btn btn-lime">Смотреть вещи <ArrowRight size={18} /></Link></div></section><section className="container about-content"><div className="section-heading"><div><span className="section-label">КАК ЭТО РАБОТАЕТ</span><h2>Просто, как поделиться с другом</h2></div></div><div className="about-steps"><div><span>01</span><Search size={30} /><h3>Найди вещь</h3><p>Листай каталог или ленту, используй категории и поиск.</p></div><div><span>02</span><UserRound size={30} /><h3>Напиши владельцу</h3><p>Открой карточку и свяжись со студентом напрямую.</p></div><div><span>03</span><Heart size={30} /><h3>Забери бесплатно</h3><p>Договоритесь о встрече и подари вещи новую историю.</p></div></div><div className="about-values"><div className="mission-circle"><Recycle size={70} /></div><div><span className="section-label">НАША ИДЕЯ</span><h2>Хорошие вещи заслуживают продолжения.</h2><p>Нам нравится идея кампуса, где меньше вещей отправляется в мусор, а больше студентов помогают друг другу. Здесь нет ценников: только полезные находки, обмен и забота о ресурсах.</p></div></div></section></main>
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
  async function remove(item) {
    if (!window.confirm(`Удалить объявление «${item.title}»?`)) return
    setBusyId(item.id)
    setError('')
    try {
      await api(`/listings/${item.id}`, { method: 'DELETE' })
      setItems(current => current.filter(entry => entry.id !== item.id))
    } catch (e) { setError(e.message) } finally { setBusyId(null) }
  }
  return <main className="page"><div className="page-hero"><div className="container"><span className="section-label">КОМАНДА CURU</span><h1>Управление объявлениями<span className="accent-dot">.</span></h1><p>Все объявления сообщества, включая забронированные и переданные.</p></div></div><div className="container admin-listings">{error && <div className="notice error">{error}</div>}{loading ? <div className="loading">Загружаем объявления...</div> : items.length ? <div className="my-items">{items.map(item => <div className="my-item admin-item" key={item.id}><div className="my-item-image">{item.image ? <img src={item.image} alt="" /> : <Gift size={24} />}</div><div><Link to={`/listing/${item.id}`}><strong>{item.title}</strong></Link><small>{item.owner.name} · {item.category} · {dateText(item.created_at)}</small></div><span className={`status-pill status-${item.status}`}>{statusLabels[item.status]}</span><button className="link-danger" disabled={busyId === item.id} onClick={() => remove(item)}>Удалить</button></div>)}</div> : <Empty title="Объявлений пока нет" />}{!loading && <div className="admin-pagination"><button className="btn btn-primary btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>Назад</button><span>Страница {Math.floor(offset / 100) + 1}</span><button className="btn btn-primary btn-sm" disabled={items.length < 100} onClick={() => setOffset(offset + 100)}>Далее</button></div>}</div></main>
}

export default function App() {
  const [user, setUser] = useState(() => { try { return JSON.parse(localStorage.getItem('curu_user') || 'null') } catch { return null } })
  function onAuth(data) { localStorage.setItem('curu_token', data.token); localStorage.setItem('curu_user', JSON.stringify(data.user)); setUser(data.user) }
  function updateUser(data) { localStorage.setItem('curu_user', JSON.stringify(data)); setUser(data) }
  function onLogout() { localStorage.removeItem('curu_token'); localStorage.removeItem('curu_user'); setUser(null) }
  return <><Header user={user} onLogout={onLogout} /><Routes><Route path="/" element={<Home />} /><Route path="/catalog" element={<Catalog />} /><Route path="/feed" element={<Feed />} /><Route path="/listing/:id" element={<ListingDetail user={user} />} /><Route path="/auth" element={<Auth onAuth={onAuth} />} /><Route path="/create" element={<Create user={user} />} /><Route path="/profile" element={<Profile user={user} setUser={updateUser} onLogout={onLogout} />} /><Route path="/admin" element={<AdminListings user={user} />} /><Route path="/student/:id" element={<Student />} /><Route path="/about" element={<About />} /><Route path="*" element={<main className="container simple-page"><Empty title="Страница не найдена" text="Возможно, ссылка устарела." /><Link className="btn btn-primary" to="/">На главную</Link></main>} /></Routes><Footer /></>
}
