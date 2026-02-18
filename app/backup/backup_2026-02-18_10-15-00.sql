--
-- PostgreSQL database dump
--

\restrict QNNlF0iDagfLyNcnzwbnZsxktXbMK41P9t4Hg12q4mxQevMpq6l8eZ2Od5aRB7v

-- Dumped from database version 18.1 (Debian 18.1-1.pgdg12+2)
-- Dumped by pg_dump version 18.2

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: clientes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clientes (
    id integer NOT NULL,
    nome_cliente character varying(100) NOT NULL,
    documento character varying(50) NOT NULL,
    contato character varying(100),
    telefone character varying(20),
    email character varying(100),
    endereco character varying(255)
);


--
-- Name: clientes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clientes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clientes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clientes_id_seq OWNED BY public.clientes.id;


--
-- Name: equipe_pilotos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.equipe_pilotos (
    id integer NOT NULL,
    equipe_id integer NOT NULL,
    piloto_id integer NOT NULL,
    papel character varying(20) NOT NULL,
    criado_em timestamp without time zone NOT NULL
);


--
-- Name: equipe_pilotos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.equipe_pilotos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: equipe_pilotos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.equipe_pilotos_id_seq OWNED BY public.equipe_pilotos.id;


--
-- Name: equipe_uvis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.equipe_uvis (
    id integer NOT NULL,
    uvis_usuario_id integer NOT NULL,
    nome_equipe character varying(100) NOT NULL,
    ordem integer NOT NULL,
    nome character varying(100) NOT NULL,
    funcao character varying(80),
    contato character varying(80),
    criado_em timestamp without time zone NOT NULL,
    CONSTRAINT ck_equipe_uvis_ordem_1_5 CHECK (((ordem >= 1) AND (ordem <= 5)))
);


--
-- Name: equipe_uvis_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.equipe_uvis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: equipe_uvis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.equipe_uvis_id_seq OWNED BY public.equipe_uvis.id;


--
-- Name: equipes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.equipes (
    id integer NOT NULL,
    nome_equipe character varying(100) NOT NULL,
    descricao text,
    regiao character varying(20),
    ativa boolean NOT NULL,
    criada_em timestamp without time zone NOT NULL
);


--
-- Name: equipes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.equipes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: equipes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.equipes_id_seq OWNED BY public.equipes.id;


--
-- Name: notificacoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notificacoes (
    id integer NOT NULL,
    usuario_id integer NOT NULL,
    titulo character varying(140) NOT NULL,
    mensagem text,
    link character varying(255),
    criada_em timestamp without time zone NOT NULL,
    lida_em timestamp without time zone,
    apagada_em timestamp without time zone
);


--
-- Name: notificacoes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notificacoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notificacoes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notificacoes_id_seq OWNED BY public.notificacoes.id;


--
-- Name: piloto_uvis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.piloto_uvis (
    id integer NOT NULL,
    piloto_id integer NOT NULL,
    uvis_usuario_id integer NOT NULL,
    criado_em timestamp without time zone NOT NULL
);


--
-- Name: piloto_uvis_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.piloto_uvis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: piloto_uvis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.piloto_uvis_id_seq OWNED BY public.piloto_uvis.id;


--
-- Name: pilotos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pilotos (
    id integer NOT NULL,
    nome_piloto character varying(100) NOT NULL,
    regiao character varying(20),
    telefone character varying(20)
);


--
-- Name: pilotos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pilotos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pilotos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pilotos_id_seq OWNED BY public.pilotos.id;


--
-- Name: solicitacoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solicitacoes (
    id integer NOT NULL,
    data_agendamento date NOT NULL,
    hora_agendamento time without time zone NOT NULL,
    foco character varying(50) NOT NULL,
    tipo_visita character varying(50),
    altura_voo character varying(20),
    criadouro boolean,
    apoio_cet boolean,
    observacao text,
    area_restrita boolean NOT NULL,
    cep character varying(9) NOT NULL,
    logradouro character varying(150) NOT NULL,
    bairro character varying(100) NOT NULL,
    cidade character varying(100) NOT NULL,
    uf character varying(2) NOT NULL,
    numero character varying(20),
    complemento character varying(100),
    latitude character varying(50),
    longitude character varying(50),
    anexo_path character varying(255),
    anexo_nome character varying(255),
    protocolo character varying(50),
    justificativa character varying(255),
    data_criacao timestamp without time zone,
    status character varying(30),
    usuario_id integer NOT NULL,
    piloto_id integer,
    equipe_id integer,
    perimetro_planejado text,
    perimetro_executado text,
    equipe_uvis_nome character varying(100)
);


--
-- Name: solicitacoes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solicitacoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solicitacoes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solicitacoes_id_seq OWNED BY public.solicitacoes.id;


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id integer NOT NULL,
    nome_uvis character varying(100) NOT NULL,
    regiao character varying(50),
    codigo_setor character varying(10),
    login character varying(50) NOT NULL,
    senha_hash character varying(200) NOT NULL,
    tipo_usuario character varying(20),
    piloto_id integer
);


--
-- Name: usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuarios_id_seq OWNED BY public.usuarios.id;


--
-- Name: clientes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes ALTER COLUMN id SET DEFAULT nextval('public.clientes_id_seq'::regclass);


--
-- Name: equipe_pilotos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipe_pilotos ALTER COLUMN id SET DEFAULT nextval('public.equipe_pilotos_id_seq'::regclass);


--
-- Name: equipe_uvis id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipe_uvis ALTER COLUMN id SET DEFAULT nextval('public.equipe_uvis_id_seq'::regclass);


--
-- Name: equipes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipes ALTER COLUMN id SET DEFAULT nextval('public.equipes_id_seq'::regclass);


--
-- Name: notificacoes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notificacoes ALTER COLUMN id SET DEFAULT nextval('public.notificacoes_id_seq'::regclass);


--
-- Name: piloto_uvis id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piloto_uvis ALTER COLUMN id SET DEFAULT nextval('public.piloto_uvis_id_seq'::regclass);


--
-- Name: pilotos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pilotos ALTER COLUMN id SET DEFAULT nextval('public.pilotos_id_seq'::regclass);


--
-- Name: solicitacoes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes ALTER COLUMN id SET DEFAULT nextval('public.solicitacoes_id_seq'::regclass);


--
-- Name: usuarios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
c7248594d6e9
\.


--
-- Data for Name: clientes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.clientes (id, nome_cliente, documento, contato, telefone, email, endereco) FROM stdin;
\.


--
-- Data for Name: equipe_pilotos; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.equipe_pilotos (id, equipe_id, piloto_id, papel, criado_em) FROM stdin;
3	2	1	piloto	2026-02-10 13:02:27.279369
4	2	2	auxiliar	2026-02-10 13:02:27.279374
\.


--
-- Data for Name: equipe_uvis; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.equipe_uvis (id, uvis_usuario_id, nome_equipe, ordem, nome, funcao, contato, criado_em) FROM stdin;
7	7	Supervisão	1	Henrique	Supervisor	supervisor@gmail.com	2026-02-10 13:09:13.294296
12	16	SP-01	1	joao	supervisor	\N	2026-02-11 12:35:28.677727
\.


--
-- Data for Name: equipes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.equipes (id, nome_equipe, descricao, regiao, ativa, criada_em) FROM stdin;
2	SP-01	\N	OESTE	t	2026-02-10 13:02:27.274428
\.


--
-- Data for Name: notificacoes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.notificacoes (id, usuario_id, titulo, mensagem, link, criada_em, lida_em, apagada_em) FROM stdin;
1	7	Agendamento para hoje	Você tem um agendamento hoje às 16:00 (Foco: Imóvel Abandonado).	/agenda?sid=22&d=2026-02-09	2026-02-09 09:35:15.731488	\N	2026-02-09 22:41:01.148005
2	7	Agendamento para hoje	Você tem um agendamento hoje às 12:00 (Foco: Imóvel Abandonado).	/agenda?sid=2&d=2026-02-09	2026-02-09 09:35:16.578201	\N	2026-02-09 22:41:01.148005
3	7	Agendamento para hoje	Você tem um agendamento hoje às 11:00 (Foco: Piscina / Caixa D'água).	/agenda?sid=37&d=2026-02-09	2026-02-09 09:35:39.155563	\N	2026-02-09 22:41:01.148005
4	7	Agendamento para hoje	Você tem um agendamento hoje às 12:00 (Foco: Ponto Estratégico (PE)).	/agenda?sid=16&d=2026-02-09	2026-02-09 09:35:53.427179	\N	2026-02-09 22:41:01.148005
5	7	Agendamento para hoje	Você tem um agendamento hoje às 10:00 (Foco: Piscina / Caixa D'água).	/agenda?sid=20&d=2026-02-10	2026-02-09 22:39:33.187066	\N	2026-02-09 22:41:01.148005
6	7	Agendamento para hoje	Você tem um agendamento hoje às 10:00 (Foco: Piscina / Caixa D'água).	/agenda?sid=4&d=2026-02-10	2026-02-09 22:39:33.20876	\N	2026-02-09 22:41:01.148005
7	7	Agendamento para hoje	Você tem um agendamento hoje às 10:00 (Foco: Imóvel Abandonado).	/agenda?sid=45&d=2026-02-11	2026-02-11 09:12:55.73214	\N	2026-02-12 22:03:59.885411
8	7	Agendamento para hoje	Você tem um agendamento hoje às 13:00 (Foco: Imóvel Abandonado).	/agenda?sid=43&d=2026-02-11	2026-02-11 09:16:38.410258	\N	2026-02-12 22:03:59.885411
9	16	Agendamento para hoje	Você tem um agendamento hoje às 13:50 (Foco: Imóvel Abandonado).	/agenda?sid=46&d=2026-02-11	2026-02-11 09:27:22.634786	2026-02-11 09:27:26.97742	2026-02-12 22:03:59.885411
10	16	Agendamento para hoje	Você tem um agendamento hoje às 12:40 (Foco: Ponto Estratégico (PE)).	/agenda?sid=48&d=2026-02-12	2026-02-12 08:40:58.675109	\N	2026-02-12 22:03:59.885411
11	16	Agendamento para hoje	Você tem um agendamento hoje às 13:50 (Foco: Imóvel Abandonado).	/agenda?sid=46&d=2026-02-12	2026-02-12 08:40:58.693558	\N	2026-02-12 22:03:59.885411
12	16	Agendamento para hoje	Você tem um agendamento hoje às 17:09 (Foco: Piscina / Caixa D'água).	/agenda?sid=47&d=2026-02-12	2026-02-12 08:40:58.702126	\N	2026-02-12 22:03:59.885411
\.


--
-- Data for Name: piloto_uvis; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.piloto_uvis (id, piloto_id, uvis_usuario_id, criado_em) FROM stdin;
\.


--
-- Data for Name: pilotos; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pilotos (id, nome_piloto, regiao, telefone) FROM stdin;
1	Piloto 01	OESTE	11999999999
2	Piloto 2	LESTE	11999999999
\.


--
-- Data for Name: solicitacoes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.solicitacoes (id, data_agendamento, hora_agendamento, foco, tipo_visita, altura_voo, criadouro, apoio_cet, observacao, area_restrita, cep, logradouro, bairro, cidade, uf, numero, complemento, latitude, longitude, anexo_path, anexo_nome, protocolo, justificativa, data_criacao, status, usuario_id, piloto_id, equipe_id, perimetro_planejado, perimetro_executado, equipe_uvis_nome) FROM stdin;
51	2026-02-20	07:00:00	Piscina / Caixa D'água	Aedes	20m	f	t		t	02031020	Rua Santa Eulália	Santana	São Paulo	SP	86	DVZ	-23.5122845	-46.6277584	\N	\N	\N	\N	2026-02-13 15:57:06.319004	PENDENTE	7	\N	\N	\N	\N	\N
59	2026-02-20	07:00:00	Ponto Estratégico (PE)	Monitoramento	20m	f	t		f	01246-904	Avenida Doutor Arnaldo	Pacaembu	São Paulo	SP	715	USP	-23.5543425	-46.6724906	\N	\N	\N	\N	2026-02-13 16:50:59.225076	PENDENTE	37	\N	\N	\N	\N	\N
58	2026-02-20	07:00:00	Imóvel Abandonado	Aedes	20m	f	f		f	02019020	Rua Andrade Figueira	Santana	São Paulo	SP	85		-23.4975913	-46.629436	\N	\N	\N	\N	2026-02-13 16:25:58.433303	CANCELADO	7	\N	\N	\N	\N	\N
60	2026-02-13	20:00:00	Piscina / Caixa D'água	Aedes	20m	f	t	teste desenvolvimento.	f	37504500	Rua Augusto de Souza Cardoso	Rebourgeon	Itajubá	MG	SN		-22.4428751	-45.4735444	\N	\N	\N	\N	2026-02-13 14:25:28.531693	CANCELADO	7	\N	\N	\N	\N	\N
\.


--
-- Data for Name: usuarios; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.usuarios (id, nome_uvis, regiao, codigo_setor, login, senha_hash, tipo_usuario, piloto_id) FROM stdin;
2	Usuário Operário	OPERACIONAL	98	operario	scrypt:32768:8:1$swvWYcB7VVc9VSWs$b58a9496496ddc5ab52b079f5692ec510ee5910ce44eabd9630bad1fc0e94ff0c1459f1b9ef3e5c28d8d1c93dbbf496470d7cd047548e84c9c78f9e702ba23b8	operario	\N
3	AUDITORIA	AUDITORIA	99	visualizar	scrypt:32768:8:1$ZhldxImsB2J6NZfL$08f93adb0750bdfffa14f8279c26b0e23338392c5ecfa11cbf707b474fe2e99694b12d56f4250533948b58c4e8e6ecc8ac3cd0f8f6c838fa6c6e516ab744027f	visualizar	\N
4	COVISA	COVISA	99	covisa	scrypt:32768:8:1$aT1SoAPOYSsybele$9f1b7d1438debb4644dbd6fc6cf2c570a746643ce309458f9e9caa967fea3c688315c7b5666b1cbee8a577d91c2ec6f520d367a5637af0c4ab3a730950483882	visualizar	\N
6	Piloto 01	OESTE	P1	piloto	scrypt:32768:8:1$BKaarLOxes4Fo0lJ$a177b94eb9f7fcbb2738b25b31924a00a84157674aa7364be690f88433668222f0ec0e705da71c1097416dea83770e834c974c4e91089f926f4b6dccb0d29f0c	piloto	1
7	UVIS Sé	CENTRO	\N	uvis.se	scrypt:32768:8:1$zt4cP7XFTCi24XFw$8d0f3673ba7927b13dd14af732e78215839772cfea28da1814cf5eeb4d31ba5af537a0a908f2cef3bab44ff2dae8be0560c9849ffb77e2d4ef43ef6fedf63d4d	uvis	\N
8	UVIS Butantã	OESTE	\N	uvis.butanta	scrypt:32768:8:1$3kki5xIfxMNB9b16$841ab0d77540691e16e96b39d9a1d2072e38e6e2887db4832dae16aa3b611245b0adfaea70bc0ecdfff76bd828e4a0a32736eb7e49a731a7e2c0154ca6fe0f54	uvis	\N
9	UVIS Santa Cecília	CENTRO	\N	uvis.santa	scrypt:32768:8:1$7MwGzk6FiEk80DxL$c5db33e1a4550c1bf01b89d09a6f35a5f65a3994958fb9cf277abbb5c309930000559f0fdf7456ad3d7bd0b428068cf97e3e3c21a8ef5e1a8838263e09f7f4b3	uvis	\N
10	UVIS Campo Limpo	SUL	\N	uvis.campo	scrypt:32768:8:1$WFi2pk4KiGhtSsIS$d7da37e052819e8ea8bdbb33f16b43ae2441a849e3b4e7241e148c3dd310d7e8a78c09be36f8e31b7ce5d5cbde90607e8060af6726d39f87ebae85cf99cfb797	uvis	\N
11	UVIS M'Boi Mirim	SUL	\N	uvis.boimirim	scrypt:32768:8:1$MtnNey8Z6F6LTv4A$bbbdab3a5fb61d2f685297561c3e432cff8b20548819d3022c877c79e4e37ad119f04328d98e04f79cf9b0d677515bd821e05a437f8dfcc87c70fc5fbb16a408	uvis	\N
12	UVIS Capela do Socorro	SUL	\N	uvis.capela	scrypt:32768:8:1$TcwsnWtvILP6pMO4$eb15d2caac87e85846e0214bf3295f0356972018f56dbc5562ec2ed4b3cdd48b3f1c05cb2d2e4b9b7272bf0c596e68919569a3a9af9080eccf51de97bf969c41	uvis	\N
13	UVIS Parelheiros	SUL	\N	uvis.paralheiros	scrypt:32768:8:1$JFmTZhqlhypaaOIr$ff2bbb13ae38ba4eecb33c3e0a189960dc677340aa6fc7e54fd80af654930f46d8c1988d95844d5588c525861ecc85216d456dd21c339f3e4d7742bdbf8438ab	uvis	\N
14	UVIS Ipiranga	SUDESTE	\N	uvis.ipiranga	scrypt:32768:8:1$gQcrYfQjThnbiXKt$6ca300f540c85290d02d2e4a7541d952c5b992ed56e489ba90f5d5e9adf093e6f21e9fb4d4491e5ce2fc63dd0888b8e5f6eb3a738d023646eceddb991428d8ec	uvis	\N
15	UVIS Mooca / Aricanduva	SUDESTE	\N	uvis.mooca	scrypt:32768:8:1$QMgA43RldEN9Arp9$6a328d1383d7dd3e46232c20042db183d077e170afcafaa717438d33aff1ddb1e512e175349f93be58cd33dd266355a07f5818c900d5be6fe26c6d1cbb06ea3c	uvis	\N
16	UVIS Penha	SUDESTE	\N	uvis.penha	scrypt:32768:8:1$XYr3V5P3B1OIAPI0$be8736a6dde16af049f4a474dd230773df107f8889dbb3ec348d392d0a3bcb7b0ab016cff93bc768d9896174a91f2b323fa5146bdef4345b1b72b160ec9e7734	uvis	\N
17	UVIS Vila Prudente / Sapopemba	SUDESTE	\N	uvis.vilaprudente	scrypt:32768:8:1$coznWpmc1UPFUzHn$1f1bc724f5432fe5739793074c8a0c89c0fa7681bd58a2ae61f7ad08e8a53e94006e4c0801bf0100586a5b9462095f5f27340f0887d562ad9ceae27582793e67	uvis	\N
18	UVIS Casa Verde / Cachoeirinha	NORTE	\N	uvis.casaverde	scrypt:32768:8:1$nLQIMko04nOlI3Wb$9e62e060e236ccfb1313259896f16948c396736435788b7a49f00f5da6f38d34474ddf8c665a8976a3af3fe8c679729f6e8f3a06c33154f5bada1bde00c46867	uvis	\N
19	UVIS Freguesia do Ó / Brasilândia	NORTE	\N	uvis.brasilandia	scrypt:32768:8:1$PKI3mAkuCWtuzJ9y$89c6cb1fce8650aef396fd20dbdc7d69da9c8579fff3d86089e06202c14d6286b3528414b748b9df351f48ccdd6d71cda1af86e522b64c5b673f3d55b8326343	uvis	\N
20	UVIS Perus	NORTE	\N	uvis.perus	scrypt:32768:8:1$TsEw9ILBwleBydzK$a59aa96dfaae9de53ad7b0a932c28f487b6f86973ea10ad41bc6f0c624c4d9dc8b7f4f6e42f6893c6e580f95caba27f7d93dc27c9f428621dbabe033ddf29550	uvis	\N
21	UVIS Jaçanã / Tremembé	NORTE	\N	uvis.jacana	scrypt:32768:8:1$8l060jYarW7d9tot$94d56b9154635bface15ad4a9698ab307f895dd1a62f39ce060d4e9f6124f045e900a1ca8916e236849328a2069996f0ae5a46599ab13997e0b9c4bd1057c0ff	uvis	\N
22	UVIS Santana / Tucuruvi	NORTE	\N	uvis.santana	scrypt:32768:8:1$3G0gK3DSxP0jF2sB$b6bd7b43c02bdec2534b194d74aeb4d57f295c4a7c97b59ca797933c88042b1f6dc418bac60c6650d799e708d270106861097bc24f12dace85d1cefebda8fe37	uvis	\N
23	UVIS Vila Maria / Vila Guilherme	NORTE	\N	uvis.vilamaria	scrypt:32768:8:1$3XU2yXui2n4zCrPn$afc49805c4c3dedaa8cb2185f15cd8880218168a943bc924cf4fc5a2e07af99c6dd4a27a982331721e3bf272d6f5c3fb7fa8896ddf7f782909afb91e25af6d18	uvis	\N
24	UVIS Pirituba	NORTE	\N	uvis.pirituba	scrypt:32768:8:1$E1Uvp6CLu6X687Lf$bf9d73f87efb465735ab80058225e484c63e8ab15d55c50a96079e4bfcb73ff3c31750c79a1d1429b32e09185a09250a4ba94fcbb84bada0c049f14639e8c695	uvis	\N
25	UVIS Cidade Tiradentes	LESTE	\N	uvis.tiradentes	scrypt:32768:8:1$z1WCd5Lq6iXuGfj7$f68f9ae5f6d9d0954826fef774b05ead740ff0a34e26350fa5b50f9c44778e3af774e4874007f11351a596eade717f9f9e793ff46651f4d3302057469be0e556	uvis	\N
26	UVIS Guaianases	LESTE	\N	uvis.guaianases	scrypt:32768:8:1$U3aQjp1vlGsZDN5I$4689929c10355f3b4ae87c3345858c3df27625c28852f60cae0df49c3b3add88a3600f7fe0b7c47a04e26cd600cbbf1caf14b082e1b8bb5d183a3607f500c2c7	uvis	\N
27	UVIS Itaquera	LESTE	\N	uvis.itaquera	scrypt:32768:8:1$28dGul9a3EOd7Cy8$ad6072e58e27e2ffe9824cc04365dd5a1caebb87dd18a9500b7ffc452efc4cb6b952be03512bb9ea3529f4c50bc28d1e638e97dcaacdf61ee3e2448d348f244f	uvis	\N
28	UVIS Ermelino Matarazzo	LESTE	\N	uvis.ermelino	scrypt:32768:8:1$gC4xGp1374LNzT1f$f99fa410ce50e988e6781d89f1f39b34fd742ce260f9d0e2f20614fee3cb57b783cd4878d373efc73a5885f2898d72356130947adc0a416f1dfc3deca1c19dc5	uvis	\N
29	UVIS Itaim Paulista	LESTE	\N	uvis.itaim	scrypt:32768:8:1$eXXaSXlClxkhbiA8$7a2552e856ec76ed7561922e929647966b73c4aa103f038a79465eb9dad38c8bf206b24a93ed6ef7497e12d255b4dac3c96ecd8af0900d7551a69b6b7a244f7a	uvis	\N
30	UVIS São Mateus	LESTE	\N	uvis.saomateus	scrypt:32768:8:1$Zh34T5TfD3VeMZfQ$44217ed9a34d3a2e239af6f19bae845e433a30bb1ee67abd510cf756a33c13a036b706deffcb21cd952feec83d5050e27cf2b42e8bc518bc312f9b35e14cb7ee	uvis	\N
31	UVIS São Miguel	LESTE	\N	uvis.saomiguel	scrypt:32768:8:1$PgzsYklUEbLZfN3e$2b587bc944de9fff5b59ebcb64d67637fb378890515d7e819d79addbc671809be58cd254345fa8edaadc6c1b6fbda831b63f05aea0bde9d1239bd525b074581a	uvis	\N
1	ADMIN	\N	\N	admin	scrypt:32768:8:1$0Docxqcx8HhRlsKm$c7f2455202ad48a42ec93a3cfb8ee3fbbe72c92e52a674bcf773f11918ed8398d16aca4b8aaaf521eaa4f813b173883e0e9ae5dc420442756adf5f6ab98c26c8	admin	\N
32	Dev João	CENTRO-OESTE	\N	dev.joao	scrypt:32768:8:1$NL2M7llOwuWXqRS1$57a5ebf200c5f00806550fed4c3d175bebb9edc0256705da73f5db031e061a72adb8a7e7924afaa74d6de72fbd8e0b9fde3a09148e5ffeb4dc2208ad4b8661ca	admin	\N
34	Enzo	SUL	\N	enzo	scrypt:32768:8:1$GKCgc4UAWJP3KKdi$080ce8fcac78a819aa82f3bf21b8dc96d2ab3682ae6f0571e6cd1d6416b5cb1e646832fe76c0c2323ef88b3d4eb73b9481bc745a3f503f2b8aded62026c171b7	admin	\N
35	Guilherme Suporte	SUL	\N	sup.guilherme	scrypt:32768:8:1$x5DfkwKqSUacTmS3$0dd5e4a61135ffe1df0a2dc5ff40b3adae23814418a6bb29fb3aa39979180b32dbc8126d1821c68fc93a9d8b37f2f34b4a5aae3c6d042ac8614b5d4042f0415b	admin	\N
36	Pedro Carniello Suporte	SUL	\N	sup.pedro	scrypt:32768:8:1$XMJXxVZ2ybREU5f9$5f3dd838b35d761e706fff63020ac4772c1c55946c5f0e2ed71b5de319e5de9a5dfe75d102117028fa75218c5a5af762729c97a4e870b76e981c142b250e8148	admin	\N
38	Piloto 2	LESTE	\N	piloto2	scrypt:32768:8:1$q6h9LhBcOMPRB9Su$8499056bd9c9933554ab2efb99ae0e7bb7e8bf52e7d47781a12563ba3136371ceedf1ca98eb70e3bf2d7241a723fcb9ae4ab8c39940b4d93abba484a4151f6a4	piloto	2
33	Dev Ph	SUL	\N	dev.ph	scrypt:32768:8:1$CAqUSsm9pG3j9Ssn$f773b8796609e18bd2e00c52c7608ae342ca0b33a89bd1546b135d3489c103efef5b7997b0889c4171cf32642bcfc9710b1eb9be60986013e8b40bf923c3fb5e	admin	\N
40	Pedro Muntaner	OPERACIONAL	\N	admin.pedro	scrypt:32768:8:1$xTXdd9bodg2T0j8k$d6766697537a5d3becfbe51283a6f39cd3976d5dc982c8efe11a80852e9b7d825c4c51afe7d56cd598299008ad0358580a9b0b6047efe235737e923106191d59	admin	\N
37	UVIS Lapa/Pinheiros	OESTE	\N	uvis.lapa	scrypt:32768:8:1$Z6yOJamOtEU8dPsb$1edfa8d9b414c5bce7f569ac579404f02e5950b8b31ad91ee0e9f7239d1e09f57ff1f582f11e04583fb256d133290f1b104aabe77e38ab401e6f888e08646529	uvis	\N
41	Operario 2	OPERACIONAL	\N	op.op	scrypt:32768:8:1$S5Iy237K1zOMTnZX$10452aea743ec20f9d27a24667545bd48f40416435f9eacd043e591707f870bf1ff476e8b23f5370f5d9fdc4bccca72f19303bd8e326cc67c368fe7db5378fe9	operario	\N
\.


--
-- Name: clientes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.clientes_id_seq', 1, false);


--
-- Name: equipe_pilotos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.equipe_pilotos_id_seq', 4, true);


--
-- Name: equipe_uvis_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.equipe_uvis_id_seq', 12, true);


--
-- Name: equipes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.equipes_id_seq', 2, true);


--
-- Name: notificacoes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.notificacoes_id_seq', 12, true);


--
-- Name: piloto_uvis_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.piloto_uvis_id_seq', 1, true);


--
-- Name: pilotos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.pilotos_id_seq', 2, true);


--
-- Name: solicitacoes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.solicitacoes_id_seq', 60, true);


--
-- Name: usuarios_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.usuarios_id_seq', 41, true);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: clientes clientes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT clientes_pkey PRIMARY KEY (id);


--
-- Name: equipe_pilotos equipe_pilotos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipe_pilotos
    ADD CONSTRAINT equipe_pilotos_pkey PRIMARY KEY (id);


--
-- Name: equipe_uvis equipe_uvis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipe_uvis
    ADD CONSTRAINT equipe_uvis_pkey PRIMARY KEY (id);


--
-- Name: equipes equipes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipes
    ADD CONSTRAINT equipes_pkey PRIMARY KEY (id);


--
-- Name: notificacoes notificacoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notificacoes
    ADD CONSTRAINT notificacoes_pkey PRIMARY KEY (id);


--
-- Name: piloto_uvis piloto_uvis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piloto_uvis
    ADD CONSTRAINT piloto_uvis_pkey PRIMARY KEY (id);


--
-- Name: pilotos pilotos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pilotos
    ADD CONSTRAINT pilotos_pkey PRIMARY KEY (id);


--
-- Name: solicitacoes solicitacoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes
    ADD CONSTRAINT solicitacoes_pkey PRIMARY KEY (id);


--
-- Name: equipe_pilotos uq_equipe_papel_unico; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipe_pilotos
    ADD CONSTRAINT uq_equipe_papel_unico UNIQUE (equipe_id, papel);


--
-- Name: equipe_pilotos uq_equipe_piloto_unico; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipe_pilotos
    ADD CONSTRAINT uq_equipe_piloto_unico UNIQUE (equipe_id, piloto_id);


--
-- Name: equipe_uvis uq_equipe_uvis_equipe_slot; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipe_uvis
    ADD CONSTRAINT uq_equipe_uvis_equipe_slot UNIQUE (uvis_usuario_id, nome_equipe, ordem);


--
-- Name: piloto_uvis uq_piloto_uvis; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piloto_uvis
    ADD CONSTRAINT uq_piloto_uvis UNIQUE (piloto_id, uvis_usuario_id);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: ix_clientes_documento; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_clientes_documento ON public.clientes USING btree (documento);


--
-- Name: ix_clientes_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clientes_email ON public.clientes USING btree (email);


--
-- Name: ix_clientes_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clientes_id ON public.clientes USING btree (id);


--
-- Name: ix_clientes_nome_cliente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clientes_nome_cliente ON public.clientes USING btree (nome_cliente);


--
-- Name: ix_equipe_pilotos_criado_em; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_pilotos_criado_em ON public.equipe_pilotos USING btree (criado_em);


--
-- Name: ix_equipe_pilotos_equipe; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_pilotos_equipe ON public.equipe_pilotos USING btree (equipe_id);


--
-- Name: ix_equipe_pilotos_equipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_pilotos_equipe_id ON public.equipe_pilotos USING btree (equipe_id);


--
-- Name: ix_equipe_pilotos_papel; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_pilotos_papel ON public.equipe_pilotos USING btree (papel);


--
-- Name: ix_equipe_pilotos_piloto; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_pilotos_piloto ON public.equipe_pilotos USING btree (piloto_id);


--
-- Name: ix_equipe_pilotos_piloto_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_pilotos_piloto_id ON public.equipe_pilotos USING btree (piloto_id);


--
-- Name: ix_equipe_uvis_criado_em; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_uvis_criado_em ON public.equipe_uvis USING btree (criado_em);


--
-- Name: ix_equipe_uvis_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_uvis_nome ON public.equipe_uvis USING btree (nome);


--
-- Name: ix_equipe_uvis_nome_equipe; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_uvis_nome_equipe ON public.equipe_uvis USING btree (nome_equipe);


--
-- Name: ix_equipe_uvis_uvis; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_uvis_uvis ON public.equipe_uvis USING btree (uvis_usuario_id);


--
-- Name: ix_equipe_uvis_uvis_equipe; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_uvis_uvis_equipe ON public.equipe_uvis USING btree (uvis_usuario_id, nome_equipe);


--
-- Name: ix_equipe_uvis_uvis_equipe_ordem; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_uvis_uvis_equipe_ordem ON public.equipe_uvis USING btree (uvis_usuario_id, nome_equipe, ordem);


--
-- Name: ix_equipe_uvis_uvis_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipe_uvis_uvis_usuario_id ON public.equipe_uvis USING btree (uvis_usuario_id);


--
-- Name: ix_equipes_ativa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipes_ativa ON public.equipes USING btree (ativa);


--
-- Name: ix_equipes_criada_em; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipes_criada_em ON public.equipes USING btree (criada_em);


--
-- Name: ix_equipes_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipes_id ON public.equipes USING btree (id);


--
-- Name: ix_equipes_nome_equipe; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipes_nome_equipe ON public.equipes USING btree (nome_equipe);


--
-- Name: ix_equipes_regiao; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipes_regiao ON public.equipes USING btree (regiao);


--
-- Name: ix_notificacoes_apagada_em; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notificacoes_apagada_em ON public.notificacoes USING btree (apagada_em);


--
-- Name: ix_notificacoes_criada_em; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notificacoes_criada_em ON public.notificacoes USING btree (criada_em);


--
-- Name: ix_notificacoes_lida_em; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notificacoes_lida_em ON public.notificacoes USING btree (lida_em);


--
-- Name: ix_notificacoes_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notificacoes_usuario_id ON public.notificacoes USING btree (usuario_id);


--
-- Name: ix_piloto_uvis_criado_em; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_piloto_uvis_criado_em ON public.piloto_uvis USING btree (criado_em);


--
-- Name: ix_piloto_uvis_piloto; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_piloto_uvis_piloto ON public.piloto_uvis USING btree (piloto_id);


--
-- Name: ix_piloto_uvis_piloto_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_piloto_uvis_piloto_id ON public.piloto_uvis USING btree (piloto_id);


--
-- Name: ix_piloto_uvis_uvis; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_piloto_uvis_uvis ON public.piloto_uvis USING btree (uvis_usuario_id);


--
-- Name: ix_piloto_uvis_uvis_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_piloto_uvis_uvis_usuario_id ON public.piloto_uvis USING btree (uvis_usuario_id);


--
-- Name: ix_pilotos_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pilotos_id ON public.pilotos USING btree (id);


--
-- Name: ix_pilotos_nome_piloto; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pilotos_nome_piloto ON public.pilotos USING btree (nome_piloto);


--
-- Name: ix_solicitacao_agenda; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacao_agenda ON public.solicitacoes USING btree (data_agendamento, hora_agendamento);


--
-- Name: ix_solicitacao_data_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacao_data_status ON public.solicitacoes USING btree (data_criacao, status);


--
-- Name: ix_solicitacao_piloto_data; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacao_piloto_data ON public.solicitacoes USING btree (piloto_id, data_criacao);


--
-- Name: ix_solicitacao_usuario_data; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacao_usuario_data ON public.solicitacoes USING btree (usuario_id, data_criacao);


--
-- Name: ix_solicitacoes_altura_voo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_altura_voo ON public.solicitacoes USING btree (altura_voo);


--
-- Name: ix_solicitacoes_bairro; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_bairro ON public.solicitacoes USING btree (bairro);


--
-- Name: ix_solicitacoes_cidade; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_cidade ON public.solicitacoes USING btree (cidade);


--
-- Name: ix_solicitacoes_data_agendamento; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_data_agendamento ON public.solicitacoes USING btree (data_agendamento);


--
-- Name: ix_solicitacoes_data_criacao; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_data_criacao ON public.solicitacoes USING btree (data_criacao);


--
-- Name: ix_solicitacoes_equipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_equipe_id ON public.solicitacoes USING btree (equipe_id);


--
-- Name: ix_solicitacoes_equipe_uvis_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_equipe_uvis_nome ON public.solicitacoes USING btree (equipe_uvis_nome);


--
-- Name: ix_solicitacoes_foco; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_foco ON public.solicitacoes USING btree (foco);


--
-- Name: ix_solicitacoes_piloto_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_piloto_id ON public.solicitacoes USING btree (piloto_id);


--
-- Name: ix_solicitacoes_protocolo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_protocolo ON public.solicitacoes USING btree (protocolo);


--
-- Name: ix_solicitacoes_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_status ON public.solicitacoes USING btree (status);


--
-- Name: ix_solicitacoes_tipo_visita; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_tipo_visita ON public.solicitacoes USING btree (tipo_visita);


--
-- Name: ix_solicitacoes_uf; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_uf ON public.solicitacoes USING btree (uf);


--
-- Name: ix_solicitacoes_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_solicitacoes_usuario_id ON public.solicitacoes USING btree (usuario_id);


--
-- Name: ix_usuarios_login; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_usuarios_login ON public.usuarios USING btree (login);


--
-- Name: ix_usuarios_nome_uvis; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_nome_uvis ON public.usuarios USING btree (nome_uvis);


--
-- Name: ix_usuarios_piloto_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_piloto_id ON public.usuarios USING btree (piloto_id);


--
-- Name: ix_usuarios_regiao; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_regiao ON public.usuarios USING btree (regiao);


--
-- Name: ix_usuarios_tipo_usuario; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_usuarios_tipo_usuario ON public.usuarios USING btree (tipo_usuario);


--
-- Name: equipe_pilotos equipe_pilotos_equipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipe_pilotos
    ADD CONSTRAINT equipe_pilotos_equipe_id_fkey FOREIGN KEY (equipe_id) REFERENCES public.equipes(id);


--
-- Name: equipe_pilotos equipe_pilotos_piloto_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipe_pilotos
    ADD CONSTRAINT equipe_pilotos_piloto_id_fkey FOREIGN KEY (piloto_id) REFERENCES public.pilotos(id);


--
-- Name: equipe_uvis equipe_uvis_uvis_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipe_uvis
    ADD CONSTRAINT equipe_uvis_uvis_usuario_id_fkey FOREIGN KEY (uvis_usuario_id) REFERENCES public.usuarios(id);


--
-- Name: notificacoes notificacoes_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notificacoes
    ADD CONSTRAINT notificacoes_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: piloto_uvis piloto_uvis_piloto_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piloto_uvis
    ADD CONSTRAINT piloto_uvis_piloto_id_fkey FOREIGN KEY (piloto_id) REFERENCES public.pilotos(id);


--
-- Name: piloto_uvis piloto_uvis_uvis_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piloto_uvis
    ADD CONSTRAINT piloto_uvis_uvis_usuario_id_fkey FOREIGN KEY (uvis_usuario_id) REFERENCES public.usuarios(id);


--
-- Name: solicitacoes solicitacoes_equipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes
    ADD CONSTRAINT solicitacoes_equipe_id_fkey FOREIGN KEY (equipe_id) REFERENCES public.equipes(id);


--
-- Name: solicitacoes solicitacoes_piloto_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes
    ADD CONSTRAINT solicitacoes_piloto_id_fkey FOREIGN KEY (piloto_id) REFERENCES public.pilotos(id);


--
-- Name: solicitacoes solicitacoes_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solicitacoes
    ADD CONSTRAINT solicitacoes_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: usuarios usuarios_piloto_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_piloto_id_fkey FOREIGN KEY (piloto_id) REFERENCES public.pilotos(id);


--
-- PostgreSQL database dump complete
--

\unrestrict QNNlF0iDagfLyNcnzwbnZsxktXbMK41P9t4Hg12q4mxQevMpq6l8eZ2Od5aRB7v

