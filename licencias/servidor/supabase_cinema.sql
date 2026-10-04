-- =====================================================================================
--  Cinema Productions · Servidor de control de licencias (Supabase / PostgreSQL)
--
--  Guarda el tiempo de uso, los equipos, los avisos y el estado que tú fijas para cada licencia
--  desde el Administrador (activa, suspendida, reembolsada, revocada).
--
--  Cómo instalarlo (una sola vez):
--    1. Entra a supabase.com → tu proyecto → SQL Editor → New query.
--    2. Pega TODO este archivo y pulsa Run. Se puede volver a ejecutar sin perder datos.
--    3. En Project Settings → API Keys copia la URL del proyecto, la clave PUBLICABLE
--       (sb_publishable_…, va en tu programa) y la clave SECRETA (sb_secret_…, solo en el Administrador).
--
--  Seguridad: tu programa usa la clave publicable y SOLO puede llamar a cinema_latido y
--  cinema_aviso_leido. No puede leer las tablas, ni ver otras licencias, ni darse una licencia:
--  el servidor solo puede QUITAR permisos, nunca darlos. Tu programa nunca envía la clave de
--  licencia (envía su huella SHA-256) ni datos personales del cliente.
--
--  Creado por Cinema Productions.
-- =====================================================================================

create table if not exists public.cinema_equipos (
  licencia       text        not null,              -- huella SHA-256 de la clave
  equipo         text        not null,              -- ID corto del equipo (3F2A-91BC-04DE-77A1)
  app            text,
  nombre_equipo  text,
  so             text,
  version_app    text,
  tienda         text,
  sdk            text,
  primera_vez    timestamptz not null default now(),
  ultima_vez     timestamptz not null default now(),
  segundos_uso   bigint      not null default 0,
  sesiones       integer     not null default 0,
  primary key (licencia, equipo)
);

create table if not exists public.cinema_sesiones (
  id           uuid        primary key,
  licencia     text        not null,
  equipo       text        not null,
  inicio       timestamptz not null default now(),
  ultima       timestamptz not null default now(),
  segundos     integer     not null default 0,
  version_app  text,
  cerrada      boolean     not null default false
);
create index if not exists cinema_sesiones_licencia on public.cinema_sesiones (licencia, inicio desc);

create table if not exists public.cinema_uso_diario (
  licencia  text    not null,
  equipo    text    not null,
  dia       date    not null,
  segundos  integer not null default 0,
  primary key (licencia, equipo, dia)
);
create index if not exists cinema_uso_diario_dia on public.cinema_uso_diario (dia);

create table if not exists public.cinema_estados (
  licencia     text        primary key,
  estado       text        not null default 'activa'
               check (estado in ('activa', 'suspendida', 'reembolsada', 'revocada')),
  motivo       text,
  actualizado  timestamptz not null default now()
);

create table if not exists public.cinema_avisos (
  id            bigint      generated always as identity primary key,
  licencia      text,                                 -- null = para todas las licencias
  app           text,                                 -- null = para todos tus programas
  tipo          text        not null default 'info'
                check (tipo in ('info', 'advertencia', 'remocion', 'reactivada', 'bloqueo')),
  titulo        text        not null,
  mensaje       text        not null default '',
  fecha_limite  timestamptz,
  creado        timestamptz not null default now(),
  expira        timestamptz
);
create index if not exists cinema_avisos_licencia on public.cinema_avisos (licencia, creado desc);

create table if not exists public.cinema_avisos_leidos (
  aviso     bigint      not null references public.cinema_avisos (id) on delete cascade,
  licencia  text        not null,
  equipo    text        not null,
  leido     timestamptz not null default now(),
  primary key (aviso, licencia, equipo)
);

create table if not exists public.cinema_eventos (
  id        bigint      generated always as identity primary key,
  licencia  text,
  equipo    text,
  tipo      text        not null,                     -- activacion, desactivacion, licencia_perdida, reactivada
  detalle   text,
  creado    timestamptz not null default now()
);
create index if not exists cinema_eventos_creado on public.cinema_eventos (creado desc);

-- ------------------------------------------------------------------ seguridad
alter table public.cinema_equipos        enable row level security;
alter table public.cinema_sesiones       enable row level security;
alter table public.cinema_uso_diario     enable row level security;
alter table public.cinema_estados        enable row level security;
alter table public.cinema_avisos         enable row level security;
alter table public.cinema_avisos_leidos  enable row level security;
alter table public.cinema_eventos        enable row level security;
revoke all on public.cinema_equipos, public.cinema_sesiones, public.cinema_uso_diario, public.cinema_estados,
              public.cinema_avisos, public.cinema_avisos_leidos, public.cinema_eventos from anon, authenticated;

-- ------------------------------------------------------------------ funciones para el programa
create or replace function public.cinema_latido(p jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_lic     text    := lower(left(coalesce(p ->> 'licencia', ''), 64));
  v_equipo  text    := left(coalesce(p ->> 'equipo', ''), 40);
  v_seg     integer := greatest(0, least(coalesce(nullif(p ->> 'segundos', '')::integer, 0), 3600));
  v_inicio  boolean := coalesce(nullif(p ->> 'inicio', '')::boolean, false);
  v_fin     boolean := coalesce(nullif(p ->> 'fin', '')::boolean, false);
  v_estado  text;
  v_motivo  text;
  v_avisos  jsonb;
begin
  if v_lic !~ '^[0-9a-f]{64}$' or v_equipo = '' then
    raise exception 'datos incompletos' using errcode = '22023';
  end if;

  insert into cinema_equipos as e (licencia, equipo, app, nombre_equipo, so, version_app, tienda, sdk,
                                   segundos_uso, sesiones)
  values (v_lic, v_equipo, left(p ->> 'app', 120), left(p ->> 'nombre_equipo', 120), left(p ->> 'so', 80),
          left(p ->> 'version', 40), nullif(left(p ->> 'tienda', 20), ''), left(p ->> 'sdk', 40), v_seg,
          case when v_inicio then 1 else 0 end)
  on conflict (licencia, equipo) do update set
    ultima_vez    = now(),
    app           = coalesce(excluded.app, e.app),
    nombre_equipo = coalesce(excluded.nombre_equipo, e.nombre_equipo),
    so            = coalesce(excluded.so, e.so),
    version_app   = coalesce(excluded.version_app, e.version_app),
    tienda        = coalesce(excluded.tienda, e.tienda),
    sdk           = coalesce(excluded.sdk, e.sdk),
    segundos_uso  = e.segundos_uso + v_seg,
    sesiones      = e.sesiones + case when v_inicio then 1 else 0 end;

  if nullif(p ->> 'sesion', '') is not null then
    begin
      insert into cinema_sesiones as s (id, licencia, equipo, segundos, version_app, cerrada)
      values ((p ->> 'sesion')::uuid, v_lic, v_equipo, v_seg, left(p ->> 'version', 40), v_fin)
      on conflict (id) do update set
        ultima   = now(),
        segundos = s.segundos + v_seg,
        cerrada  = s.cerrada or v_fin
      where s.licencia = v_lic and s.equipo = v_equipo;
    exception when invalid_text_representation then
      null;   -- sesión con formato inválido: se ignora
    end;
  end if;

  if v_seg > 0 then
    insert into cinema_uso_diario as u (licencia, equipo, dia, segundos)
    values (v_lic, v_equipo, current_date, v_seg)
    on conflict (licencia, equipo, dia) do update set segundos = u.segundos + v_seg;
  end if;

  if nullif(p ->> 'evento', '') is not null then
    insert into cinema_eventos (licencia, equipo, tipo, detalle)
    values (v_lic, v_equipo, left(p ->> 'evento', 40), left(p ->> 'detalle', 300));
  end if;

  select estado, motivo into v_estado, v_motivo from cinema_estados where licencia = v_lic;

  select coalesce(jsonb_agg(jsonb_build_object('id', a.id, 'tipo', a.tipo, 'titulo', a.titulo,
                                               'mensaje', a.mensaje, 'fecha_limite', a.fecha_limite,
                                               'creado', a.creado) order by a.creado), '[]'::jsonb)
    into v_avisos
    from cinema_avisos a
   where (a.licencia = v_lic or (a.licencia is null and a.creado > now() - interval '45 days'))
     and (a.app is null or a.app = p ->> 'app')
     and (a.expira is null or a.expira > now())
     and not exists (select 1 from cinema_avisos_leidos l
                      where l.aviso = a.id and l.licencia = v_lic and l.equipo = v_equipo);

  return jsonb_build_object('estado', coalesce(v_estado, 'activa'), 'motivo', v_motivo, 'avisos', v_avisos);
end;
$$;

create or replace function public.cinema_aviso_leido(p jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into cinema_avisos_leidos (aviso, licencia, equipo)
  select a.id, lower(p ->> 'licencia'), left(p ->> 'equipo', 40)
    from cinema_avisos a
   where a.id = nullif(p ->> 'aviso', '')::bigint
     and (a.licencia is null or a.licencia = lower(p ->> 'licencia'))
     and coalesce(p ->> 'equipo', '') <> ''
  on conflict do nothing;
  return '{}'::jsonb;
end;
$$;

-- Limpieza opcional (solo con la clave secreta): borra sesiones de más de 180 días y eventos de más de un año.
create or replace function public.cinema_limpiar()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_sesiones integer;
  v_eventos  integer;
begin
  delete from cinema_sesiones where inicio < now() - interval '180 days';
  get diagnostics v_sesiones = row_count;
  delete from cinema_eventos where creado < now() - interval '365 days';
  get diagnostics v_eventos = row_count;
  return jsonb_build_object('sesiones', v_sesiones, 'eventos', v_eventos);
end;
$$;

revoke all on function public.cinema_latido(jsonb), public.cinema_aviso_leido(jsonb), public.cinema_limpiar()
  from public;
grant execute on function public.cinema_latido(jsonb), public.cinema_aviso_leido(jsonb) to anon, authenticated;
grant execute on function public.cinema_limpiar() to service_role;

comment on function public.cinema_latido(jsonb) is
  'Cinema Productions: tiempo de uso, estado de la licencia y avisos pendientes para un equipo.';
