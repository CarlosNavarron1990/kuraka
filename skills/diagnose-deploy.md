---
name: diagnose-deploy
description: "Base de conocimiento de diagnóstico de despliegue: escalera de validación genérica (localizá antes de teorizar) + catálogo de errores comunes por stack (síntoma → señal en log → causa raíz → validación rápida → fix). Se consulta en DIAGNOSE y para armar el checklist de verificación en RUNBOOK. Crece con cada incidente. On-demand."
agent: "`deploy-diagnostician` (Chaski)"
invocation: "on-demand (por incidente o al documentar un deploy)"
---

# Diagnose Deploy

Cómo localizar un fallo de despliegue/runtime **rápido**, y el catálogo de errores ya
vistos. La meta: convertir "auth OK en local, roto en el server" en un diagnóstico de 1-2
pasos en vez de 6 deploys a ciegas.

## Escalera de validación genérica (parar apenas se localiza)

1. **Síntoma en una frase + diferencia local-vs-server.** La causa casi siempre vive en esa
   diferencia: sub-aplicación virtual (hay `PathBase`), reverse proxy, TLS terminado afuera,
   permisos NTFS, identidad de proceso vs anónima, pool en Integrated vs Classic.
2. **Log de acceso primero (IIS/nginx), no el log de app.** ¿A qué ruta+verbo llega el
   request y con qué `status` / `substatus` / `win32`? Eso ya clasifica la capa:
   - `302` en loop → cookie de auth no se emite/lee.
   - `404` en la ruta del callback/handler → el middleware no interceptó; cae al router.
   - `401.3` / `win32 5` → ACL NTFS (permisos de archivo).
   - `500.19` → config (web.config inválido/heredado).
   - `500.0` intermitente en primer hit → arranque en frío / compilación de vistas.
3. **Trampa config-vs-binario.** Si "cambiaste algo" y no toma: ¿el cambio vive en config
   (toma en runtime con redeploy de config) o en el **binario** (requiere recompilar y
   redeployar el `bin\`/artefacto)? Un log de arranque que muestra el nuevo valor de config
   **solo prueba que cambió la config**, no que el binario se redeployó.
4. **Sonda de una línea.** Cuando el log de acceso no basta, poné el handler/middleware más
   temprano a loguear lo que el runtime realmente ve (verbo, ruta, `PathBase`, identidad, si
   el body es legible). Un deploy descarta varias hipótesis. Es temporal → marcala y quitala.
5. **Binary-search del pipeline.** Ubicá si el request muere antes o después de tu capa:
   ¿llega el `BeginRequest`? ¿corre tu middleware? ¿corre el handler? El primer punto donde
   NO aparece la traza es la capa culpable.
6. **Confirmá con evidencia y dá el semáforo.** Cada conclusión con una línea de log/HTTP
   real. El "semáforo" = qué línea/status debe aparecer cuando el fix esté vivo.
7. **Realimentá este catálogo** con el error nuevo (abajo).

---

## Catálogo de errores comunes

Formato: **DD-NN — título** · Stack · Síntoma · Señal · Causa raíz · Validación rápida · Fix.
Sembrado con incidentes reales del proyecto `waCertificadoNoDeudor` (IIS / .NET Framework 4.5 /
ASP.NET MVC 5 / OWIN OpenID Connect).

### DD-01 — Login OIDC en loop / callback 404 en sub-aplicación virtual
- **Stack:** IIS + OWIN Katana OpenID Connect, app en subpath (`/App`).
- **Síntoma:** login federado OK en local, loop infinito o 404 en el callback en el server;
  `MessageReceived` nunca dispara.
- **Señal:** IIS: el `POST` del callback devuelve `404`, o `302` a Login en loop. App log: no
  hay `MessageReceived` ni `AuthenticationFailed`.
- **Causa raíz:** en host System.Web bajo sub-app virtual, Katana compara `CallbackPath`
  contra `Request.PathBase + Request.Path` (ruta COMPLETA), no contra el `Request.Path`
  recortado. Un `CallbackPath` corto no matchea → el POST cae a MVC. Invisible en local
  (PathBase vacío).
- **Validación rápida:** sonda OWIN (primer `app.Use`) logueando `PathBase`/`Path`. Si
  `Path==CallbackPath` y aun así no intercepta → es esto.
- **Fix:** `CallbackPath = new PathString(new Uri(appSettings["ida:RedirectUri"]).AbsolutePath)`
  (ruta completa derivada del RedirectUri; sirve en raíz y en subpath). RedirectUri registrado
  idéntico en el IdP. Ref: `[LL-007]`.

### DD-02 — Trampa config-vs-binario (el cambio no toma)
- **Stack:** cualquiera con artefacto compilado (DLL/jar) + config externa.
- **Síntoma:** cambiaste un setting y el comportamiento no cambia; el log muestra el valor
  nuevo pero el bug persiste.
- **Señal:** el log de arranque refleja la config nueva, pero la lógica que depende del
  **código** sigue vieja.
- **Causa raíz:** se desplegó solo la config (runtime), no el binario recompilado.
- **Validación rápida:** ¿el cambio vive en config o en código? Fecha de modificación del
  DLL/artefacto en el server vs hora de compilación. Una sonda en el binario que NO aparece =
  binario viejo.
- **Fix:** recompilar y redeployar el `bin\`/artefacto; reciclar. Documentar en la matriz
  config-vs-binario del runbook qué setting vive dónde.

### DD-03 — 401.3 en archivos estáticos, pero bundles 200
- **Stack:** IIS, StaticFileModule vs handler managed (bundles).
- **Síntoma:** el CSS/JS/imagen directos dan 401 (sin estilo), pero `/bundles/*` cargan 200;
  falla igual logueado o no.
- **Señal:** IIS `sc-status 401 sc-substatus 3 sc-win32-status 5` en `.css`/`.js`/`.png`;
  `/bundles/*` = 200.
- **Causa raíz:** el App Pool tiene lectura NTFS (por eso los bundles, que lee el proceso,
  funcionan), pero la **identidad anónima (IUSR)** que sirve los estáticos NO tiene lectura.
  No es auth, es ACL.
- **Validación rápida:** confirmá `substatus 3 / win32 5` en el log de IIS.
- **Fix:** (A) IIS → Anonymous Authentication → usar "Application pool identity"; o (B)
  `icacls <app> /grant "IIS_IUSRS:(OI)(CI)(RX)" /T` y `IUSR` igual.

### DD-04 — 500.19 por header/config duplicado en sub-app
- **Stack:** IIS, app hija bajo un web.config padre.
- **Síntoma:** `500.19` al abrir la app hija.
- **Señal:** IIS `500.19` con `win32 50` (ERROR_NOT_SUPPORTED); mensaje de "duplicate
  collection entry" (p.ej. `Strict-Transport-Security`).
- **Causa raíz:** el web.config de la app hija agrega un `customHeader`/setting que el padre
  ya define → colección duplicada.
- **Validación rápida:** el detalle del 500.19 nombra la clave duplicada.
- **Fix:** hacer idempotente: `<remove name="X" />` antes del `<add name="X" .../>` en el
  web.config de la app.

### DD-05 — OWIN requiere pipeline Integrated
- **Stack:** IIS App Pool en modo Clásico + OWIN.
- **Síntoma:** excepción al arrancar/servir con OWIN.
- **Señal:** `PlatformNotSupportedException` en `HttpResponse.get_Headers()`.
- **Causa raíz:** OWIN (Katana SystemWeb host) requiere **Integrated Managed Pipeline**;
  en Clásico revienta.
- **Validación rápida:** IIS → App Pool → Managed Pipeline Mode.
- **Fix:** poner el App Pool en **Integrated** y reciclar.

### DD-06 — form_post del callback degradado a GET (RedirectUri termina en "/")
- **Stack:** IdP con `response_mode=form_post` detrás de proxy/IIS.
- **Síntoma:** el IdP autentica pero el token no llega; el callback se pierde.
- **Señal:** el `POST` del callback aparece como `GET` en el server, o con body vacío.
- **Causa raíz:** el `redirect_uri` apunta a un "directorio" (termina en `/`) → IIS/proxy
  aplica redirección de default-document (302) y degrada el POST a GET, perdiendo el body.
- **Validación rápida:** mirá el verbo real del callback en el log de acceso.
- **Fix:** `redirect_uri` a un recurso dedicado (p.ej. `/signin-oidc`), no a la raíz; y
  registrado idéntico en el IdP.

### DD-07 — "roto en local" que en realidad es red/DB, no la feature (red herring)
- **Stack:** cualquiera que dependa de DB/servicio por VPN.
- **Síntoma:** el flujo falla en un entorno; parece bug de la feature.
- **Señal:** SQL `error 40 / could not open a connection`, timeouts, DNS.
- **Causa raíz:** el entorno no alcanza la DB/servicio (VPN caída, firewall, host).
- **Validación rápida:** ¿el error es de conectividad (40/timeout) o de lógica? Probar la
  conexión cruda al recurso.
- **Fix:** arreglar conectividad (VPN/red) antes de tocar código. No perseguir un bug de
  feature que es de entorno.

### DD-08 — TLS 1.2 no habilitado (.NET Framework ≤ 4.5) contra el IdP
- **Stack:** .NET Framework 4.5, cliente saliente a endpoint que exige TLS 1.2.
- **Síntoma:** falla al descargar metadata OIDC / handshake reseteado al arrancar el
  middleware.
- **Señal:** `SocketException 0x2746`, `IDX20803`/`IDX20804`.
- **Causa raíz:** .NET 4.5 negocia TLS 1.0/1.1 por defecto; el IdP exige 1.2.
- **Validación rápida:** ¿se resetea el handshake justo al pedir el documento de metadata?
- **Fix:** `ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;` en el arranque.

---

## Cómo crecer este catálogo

Cuando Chaski diagnostica un error que no está acá, agrega una entrada **DD-NN** con el mismo
formato (síntoma · señal · causa raíz · validación rápida · fix). Si además implica una regla
de proceso (qué agente/checklist cambia para prevenirlo), crea un `[LL-00X]` en
`docs/process/lessons-learned.md` y enlazalo. El valor del catálogo es que la señal (la línea
de log/status) mapee directo a la causa: eso es lo que acorta el próximo diagnóstico.
