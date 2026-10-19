import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, ArrowUpRight, CalendarDays, ChevronLeft, ChevronRight, MapPin, ShoppingBag, Users, Ticket } from 'lucide-react'
import { api } from './api'
import { ListingCard, priceText } from './ListingCard'

const eventDate = value => new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
function useHomeData(path) {
  const [state, setState] = useState({ data: [], loading: true, error: '' })
  useEffect(() => { let active = true; api(path).then(data => { if (active) setState({ data, loading: false, error: '' }) }).catch(e => { if (active) setState({ data: [], loading: false, error: e.message }) }); return () => { active = false } }, [path])
  return state
}

export default function HubHome() {
  const events = useHomeData('/events?order=latest&limit=5')
  const market = useHomeData('/listings?limit=4')
  const [selected, setSelected] = useState(0)
  const event = events.data[selected] || events.data[0]
  const change = step => setSelected(index => (index + step + events.data.length) % events.data.length)
  return <main className="hub-home">
    <section className="container hub-welcome">
      <div><span className="section-label">CASPIANHUB / ПОРТАЛ СООБЩЕСТВА</span><h1>Всё своё.<br /><em>В одном месте.</em></h1><p>Люди, возможности и жизнь Caspian.<br />Твой колледж — ближе, чем кажется.</p></div>
      <div className="hub-destinations" aria-label="Разделы портала">
        <Link to="/events"><span className="hub-service-icon"><CalendarDays /></span><span><strong>Афиша</strong><small>События, встречи и впечатления</small></span><ArrowUpRight size={21} /></Link>
        <Link to="/market"><span className="hub-service-icon"><ShoppingBag /></span><span><strong>Маркет</strong><small>Покупай, продавай, отдавай</small></span><ArrowUpRight size={21} /></Link>
        <Link to="/profile"><span className="hub-service-icon"><Users /></span><span><strong>Мой Hub</strong><small>Твои билеты и объявления</small></span><ArrowUpRight size={21} /></Link>
      </div>
    </section>
    <section className="container hub-events" aria-labelledby="home-events-title">
      <div className="hub-section-heading"><div><span className="section-label">ЖИЗНЬ СООБЩЕСТВА</span><h2 id="home-events-title">В центре внимания</h2></div><Link className="text-link" to="/events">Вся афиша <ArrowRight size={17} /></Link></div>
      {events.loading ? <div className="hub-skeleton" role="status">Загружаем афишу…</div> : events.error ? <div className="notice error" role="alert">Не удалось загрузить афишу. {events.error}</div> : event ? <div className="hub-feature-grid">
        <div className="hub-carousel" role="region" aria-roledescription="карусель" aria-label="Последние афиши">
          <Link to={`/events/${event.id}`} className={`hub-feature ${event.banner ? 'has-banner' : ''}`}>
            {event.banner ? <img src={event.banner} alt={`Афиша: ${event.title}`} /> : <div className="hub-feature-fallback" aria-hidden="true"><span>CASPIAN<br />HUB</span><ArrowUpRight /></div>}
            <span className="hub-feature-category">{event.category}</span>
            <div className="hub-feature-caption"><span><CalendarDays size={16} />{eventDate(event.event_date)}<i />{priceText(event.ticket_price)}</span><h3>{event.title}</h3><span className="hub-feature-location"><MapPin size={15} />{event.location}</span></div><span className="hub-feature-open"><ArrowUpRight size={24} /></span>
          </Link>
          {events.data.length > 1 && <div className="hub-carousel-controls"><span aria-live="polite">{String(selected + 1).padStart(2, '0')} <span>/ {String(events.data.length).padStart(2, '0')}</span></span><div className="hub-carousel-dots">{events.data.map((e, index) => <button key={e.id} aria-label={`Афиша ${index + 1}: ${e.title}`} aria-pressed={selected === index} onClick={() => setSelected(index)} />)}</div><div><button onClick={() => change(-1)} aria-label="Предыдущая афиша"><ChevronLeft size={19} /></button><button onClick={() => change(1)} aria-label="Следующая афиша"><ChevronRight size={19} /></button></div></div>}
        </div>
        <aside className="hub-event-list"><span className="section-label">ЕЩЁ В АФИШЕ</span>{events.data.filter(e => e.id !== event.id).slice(0, 3).map(e => <Link to={`/events/${e.id}`} key={e.id}><span className="hub-mini-date"><strong>{new Date(e.event_date).getDate()}</strong><small>{new Date(e.event_date).toLocaleDateString('ru-RU', { month: 'short' })}</small></span><span><small>{e.category}</small><strong>{e.title}</strong><small>{priceText(e.ticket_price)}</small></span><ArrowUpRight size={17} /></Link>)}<div className="hub-organizer-note"><Ticket size={23} /><h3>Есть идея события?</h3><p>Создайте афишу и соберите участников в CaspianHub.</p><Link to="/events/new" className="text-link">Создать событие <ArrowRight size={16} /></Link></div></aside>
      </div> : <div className="hub-empty"><CalendarDays size={30} /><div><h3>Новые события скоро появятся здесь</h3><p>Опубликуйте первую афишу и пригласите сообщество.</p></div><Link className="btn btn-primary" to="/events/new">Создать событие <ArrowRight size={17} /></Link></div>}
    </section>
    <section className="hub-market"><div className="container"><div className="hub-section-heading"><div><span className="section-label">МАРКЕТ CASPIANHUB</span><h2>Свежие находки</h2><p>Вещи от своих. За разумную цену или просто так.</p></div><Link className="text-link" to="/market">Весь маркет <ArrowRight size={17} /></Link></div>{market.loading ? <div role="status" className="loading">Загружаем объявления…</div> : market.error ? <div className="notice error" role="alert">Не удалось загрузить маркет. {market.error}</div> : market.data.length ? <div className="item-grid">{market.data.map(item => <ListingCard key={item.id} item={item} />)}</div> : <div className="hub-empty"><ShoppingBag size={30} /><div><h3>Место для ваших объявлений</h3><p>Продайте ненужное или отдайте тому, кому это пригодится.</p></div><Link className="btn btn-primary" to="/market/new">Разместить объявление</Link></div>}</div></section>
    <section className="container hub-community"><span className="section-label">ОДНО СООБЩЕСТВО. БОЛЬШЕ ВОЗМОЖНОСТЕЙ.</span><h2>Твой Caspian.<br />Твой Hub.</h2><Link className="text-link" to="/about">О платформе <ArrowRight size={18} /></Link></section>
  </main>
}
