<!-- converted from APIReferenceGuide-Offline-Espanol.docx -->





# Descripción general de API
La API de Exchange es para los desarrolladores que buscan crear sistemas automatizados de apuestas o interfaces personalizadas de apuestas para sí mismos o para los clientes de Betfair. La API de Exchange está disponible para el Betfair Exchange (Intercambio) global, español e italiano

La API contiene un potente conjunto de características que permiten hacer una navegación avanzada por el mercado, buscar, recuperar probabilidades, hacer apuestas y recuperar datos relacionados con los deportes. La API de Exchange está formada con los siguientes componentes clave:

API de apuestas: contiene operaciones de navegación, recuperación de probabilidades y realización de apuestas.
API de cuentas: contiene operaciones relacionadas con las cuentas, como la capacidad de recuperar el balance disponible de su cuenta, así como las operaciones de los servicios de proveedores que están disponibles para los proveedores de software con licencia
API de pulso: le permite cancelar automáticamente las apuestas sin coincidencia en caso de que los clientes de su API pierdan conectividad.
API de estado de la carrera: permite establecer el estado de una carrera de caballos o del mercado de galgos, tanto antes como después del inicio de la carrera.
API de secuencia de Exchange: le permite suscribirse a los cambios del mercado (precio y definiciones) y los pedidos.



Documentación

Hay una serie de recursos de documentación disponibles:

Guía de inicio: proporciona toda la información necesaria sobre licencias, inicio de sesión y realización de primeras solicitudes a través de la API de Betfair.

Guía de referencia: la última documentación de la API de Betfair.

Código de ejemplo: hay ejemplos de código disponibles en un gran número de lenguajes de programación.

Herramientas de demostración: le permiten probar rápidamente las operaciones de API a través de una interfaz fácil de usar.

Foro de desarrolladores: analice la API de Betfair, comparta sus conocimientos y haga preguntas de la comunidad de desarrolladores.



Ventajas y características

Las principales ventajas y características de la API de Exchange incluyen lo siguiente:

El acceso a la API de Exchange es gratuito debido a fines de desarrollo*# para el uso personal únicamente de todos 
los desarrolladores.
No hay cargos de solicitud de datos para las peticiones hechas a través de la API de Exchange.
Protocolo ligero (JSON/JSON-RPC).
Configure la profundidad de los mejores precios que se le devolvieron.
Precios disponibles de acumulación: puede configurar el tipo y la cantidad de la acumulación.
Recupere datos de múltiples mercados en una sola solicitud.
Recupere los precios y las apuestas con o sin coincidencia disponibles a través de una sola solicitud.
Busque según los indicadores de MarketType (MATCH_ODDS, WIN, PLACE etc.) que siguen siendo los mismos, independientemente del idioma. Busque mercados en juego.
Vea el ‘resultado’ según la selección después del término.
Vea los precios virtuales.


* No se aplica al acceso comercial. Consulte Oportunidades comerciales para conocer los detalles de la licencia comercial

# Debe utilizar su clave de aplicación retardada para fines de desarrollo. Para solicitar una clave de aplicación en directo, haga clic aquí y seleccione Exchange API > For My Personal Betting (API de Exchange > Para mis apuestas personales) y complete el formulario de solicitud en la parte inferior de la página. Se aplica una tarifa de activación única de £299; esto se debita directamente de su cuenta de Betfair una vez que se apruebe el acceso.



Actualizado recientemente

Inicio de sesión interactivo: extremo de API
hace aproximadamente 5 horas • actualizado por Usuario incorporado • 
ver el cambio
Inicio de sesión no interactivo (robot)
hace aproximadamente 5 horas • actualizado por Usuario incorporado • 
ver el cambio
API de secuencia de Exchange
21 de abril de 2017 • actualizado por usuario incorporado • ver el cambio
Enumeraciones de apuestas
13 de abril de 2017 • actualizado por usuario incorporado • ver el cambio
Esquema de API
12 de abril de 2017 • actualizado por usuario incorporado • ver el cambio
Definiciones de tipo de apuestas
11 de abril de 2017 • actualizado por usuario incorporado • ver el cambio
Datos de navegación para las aplicaciones
10 de abril de 2017 • actualizado por usuario incorporado • ver el cambio
listRunnerBook
6 de abril de 2017 • actualizado por usuario incorporado • ver el cambio
Incrementos de precios de Betfair
6 de abril de 2017 • actualizado por usuario incorporado • ver el cambio
Mejores prácticas
6 de abril de 2017 • actualizado por usuario incorporado • ver el cambio
Claves de aplicación
6 de abril de 2017 • actualizado por usuario incorporado • ver el cambio
Ciclo de vida del desarrollo
6 de abril de 2017 • creado por usuario incorporado
API de pulso
6 de abril de 2017 • actualizado por usuario incorporado • ver el cambio
Documentos de definición de interfaz
4 de abril de 2017 • actualizado por usuario incorporado • ver el cambio
Notas de la versión
28 de marzo de 2017 • actualizado por usuario incorporado • ver el cambio

## Inicio

¿Cómo puedo empezar?
Inicio de sesión
Cómo hacer una solicitud a la API
Extremos de API
JSON
JSON-RPC
Solicitudes de ejemplo
Solicitar una lista de los tipos de eventos disponibles
Solicitar una lista de eventos para un tipo de evento
Solicitar información sobre el mercado para un evento
Carreras de Caballos: mercados de posición y ganador de hoy
Competiciones de fútbol
Precios de mercado
Cómo hacer una apuesta
Cómo hacer una apuesta de Betfair SP
Recuperación de los detalles de una apuesta hecha en un mercado
Recuperación del resultado de un mercado asentado
¿Cómo puedo empezar?

Para utilizar la API de Exchange se requiere lo siguiente:

Una cuenta de Betfair. Puede abrir una cuenta de Betfair aquí
Una clave de aplicación. Puede crear una clave de solicitud siguiendo las instrucciones que se encuentran aquí
Un sessionToken. Puede crear un token de sesión mediante cualquiera de los métodos de inicio de sesión de API o siguiendo las instrucciones que se encuentran aquí

Inicio de sesión

La API de Betfair ofrece tres flujos de inicio de sesión para desarrolladores, según el caso de uso de su aplicación:

Inicio de sesión no interactivo. Si está creando una aplicación que se ejecutará de manera autónoma, hay un flujo de inicio de sesión separado que debe seguir para asegurarse de que su cuenta permanezca segura.

Inicio de sesión interactivo. Si está creando una aplicación que se usará de forma interactiva, este es el flujo para usted. Este flujo tiene dos variantes:

Inicio de sesión interactivo, método de API: este flujo usa un extremo de API de JSON y es la forma más sencilla de empezar si desea crear su propio formulario de inicio de sesión.
Inicio de sesión interactivo, aplicación de escritorio: este flujo de inicio de sesión usa las páginas de inicio de sesión de Betfair y permite que su aplicación maneje adecuadamente todos los errores y las redirecciones de la misma manera que el sitio web de Betfair

Cómo hacer una solicitud a la API







Puede llamar la API en uno de dos extremos, según el tipo de solicitud que desee utilizar.

Extremos de API

Puede realizar solicitudes y apuestas en los mercados internacionales y del Reino Unido si accede al Exchange (Intercambio) global a través de los siguientes extremos.
Busque los detalles de los extremos de la API de apuestas actual:

Exchange (Intercambio) global



Puede realizar solicitudes para la información de la billetera de Exchange (Intercambio) del Reino Unido accediendo al Exchange (Intercambio) global a través de los siguientes extremos.


Exchange global

Consulte la documentación separada para el Exchange (Intercambio) español e italiano
JSON

Puede ENVIAR una solicitud a la API en:

https://api.betfair.com/exchange/betting/rest/v1.0/<operation name>. Por lo tanto, para llamar al método listEventTypes, haría el ENVÍO a: https://api.betfair.com/exchange/betting/rest/v1.0/listEventTypes/

Los datos del ENVÍO contienen los parámetros de la solicitud. Para listEventTypes, el único parámetro obligatorio es un filtro para seleccionar los mercados. Puede pasar un filtro vacío para seleccionar todos los mercados, en cuyo caso listEventTypes vuelve a EventTypes asociado con todos los mercados disponibles




JSON-RPC

Puede ENVIAR una solicitud a la API mediante JSON-RPC en:

https://api.betfair.com/exchange/betting/json-rpc/v1

Los datos de ENVÍO deben contener una solicitud de formato JSON-RPC válida, donde el campo “params” (Parámetros) contenga los parámetros de la solicitud y el campo “method” (Método) contenga el método de API que está llamando, especificado como “SportsAPING/v1.0/<operation name>”.

Por ejemplo, si llama la operación listCompetitions y pasa un filtro para buscar todos los mercados con un identificador de tipo de evento correspondiente a 1 (es decir, todos los mercados de fútbol), los datos del ENVÍO para el extremo de JSON-RPC sería:




Aquí hay un ejemplo rápido de un programa Python que usa JSON-RPC y devuelve la lista de EventTypes (Deportes) disponible:


Y la respuesta de lo anterior:

Solicitudes de ejemplo


Solicitar una lista de los tipos de eventos disponibles

Puede hacer una solicitud utilizando el servicio listEventTypes que devolverá una respuesta que contiene los eventTypes 
(p. ej. fútbol, carreras de caballos, etc.) que están actualmente disponibles en Betfair.




Solicitar una lista de eventos para un tipo de evento

El siguiente ejemplo muestra cómo recuperar una lista de eventos (eventIds) para un tipo de evento específico. La solicitud muestra cómo recuperar todos los eventos de fútbol que están teniendo lugar en un solo día.
















Solicitar información sobre el mercado para un evento

El siguiente ejemplo muestra cómo recuperar toda la información del mercado que pertenece a un evento (excluidos los datos 
de precios). Puede incluir uno o más identificadores de eventos en las solicitudes si permanece dentro de los límites de datos 
de mercado

















Carreras de Caballos: mercados de posición y ganador de hoy

La siguiente solicitud es un ejemplo de recuperación de los mercados de posición/ganador de las carreras de caballos disponibles para un día específico. La opción marketStartTime (desde y hasta) se debe actualizar en consecuencia.



Competiciones de fútbol

Para recuperar todas las competiciones de fútbol, se llama al eventTypeId; la operación se hace con el siguiente filtro de mercado:


El "filtro" selecciona todos los mercados que tienen un eventTypeId de 1 (que es el tipo de evento de fútbol).

A continuación, devuelve una lista de las competiciones, sus identificadores y cuántos mercados hay en cada competencia que están asociados con dichos mercados:



Precios de mercado

Una vez que haya identificado el mercado (marketId) que le interesa utilizando el servicio listMarketCatalogue, puede solicitar los precios de este mercado mediante la llamada de API listMarketBook.

Este es un ejemplo que muestra una solicitud para obtener los mejores precios (a favor y en contra) y el volumen de transacciones, incluidas las apuestas virtuales.


Cómo hacer una apuesta

Para hacer una apuesta, se requieren los parámetros de marketId y selectionId de la llamada de API listMarketCatalogue. Los siguientes parámetros harán una apuesta de Exchange (Intercambio) normal en las probabilidades de 3 para una apuesta de £2,0.

Si la apuesta se hace correctamente, se devuelve un betId en la respuesta de placeOrders


Cómo hacer una apuesta de Betfair SP

Para hacer una apuesta en una selección en Betfair SP, debe especificar los siguientes parámetros en la solicitud de placeOrders. El siguiente ejemplo haría una apuesta a favor de Betfair SP en la selección requerida para una apuesta de £2,00.

Solicitud















Recuperación de los detalles de una apuesta hecha en un mercado

Puede utilizar la solicitud listCurrentOrders para recuperar una apuesta hecha en un mercado específico.


Recuperación del resultado de un mercado asentado

Para recuperar el resultado de un mercado asentado, simplemente haga una solicitud a listMarketBook después de que el mercado se haya asentado. La respuesta indicará si la selección se asentó como “GANADOR” o “PERDEDOR” en el campo de ‘estado’ de los corredores. La información del mercado asentado está disponible durante 90 días después del término.



### Claves de aplicación


¿Qué es una clave de aplicación?
Cómo crear una clave de aplicación
Claves de aplicación en directo y retardada
Acceso a apuestas personales. Descripción general de la clave de aplicación

¿Qué es una clave de aplicación?

Para poder utilizar la API de apuestas y cuentas, debe tener una clave de aplicación. La clave de aplicación identifica a su cliente de API. Dos claves de aplicación se asignan a una sola cuenta de Betfair, una clave de aplicación en directo y una clave de aplicación retardada para probar.

Debe pasar la clave de aplicación con cada solicitud de HTTP. Esto se hace configurando el encabezado de HTTP con el valor de la clave asignada por Betfair.





Cómo crear una clave de aplicación

Puede crear una clave de aplicación para su cuenta de Betfair utilizando el visualizador de API de cuentas y la operación createDeveloperAppKeys

Haga clic en el enlace Accounts API Visualiser (Visualizador de API de cuentas) y asegúrese de que el extremo “PROD”/”UK” esté seleccionado.
Seleccione la operación createDeveloperAppKeys de la lista de operaciones en la parte superior izquierda del visualizador.
Introduzca un sessionToken en el cuadro de texto ‘Session Token (ssoid)” (Token de sesión). Puede encontrar instrucciones sobre cómo encontrar el sessionToken mediante su navegador aquí.
Introduzca el Nombre de la aplicación (debe ser único) en la columna ‘Request’ (Solicitud). Puede elegir cualquier Nombre de aplicación que desee, pero tal como su nombre de usuario de Betfair, debe ser único.
Pulse Execute (Ejecutar) en la parte inferior de la columna ‘Request’ (Solicitud).

Se crearán dos claves de aplicación y se mostrarán en la columna Developer Apps (Aplicaciones de desarrollador) de la herramienta de demostración

Tenga en cuenta lo siguiente:

- El encabezado de X-Application no es necesario cuando se utiliza el servicio createDeveloperAppKeys o getDeveloperAppKeys.
- El nombre de la aplicación debe ser único.



Claves de aplicación en directo y retardada

El servicio createDeveloperAppKeys asignará dos claves de aplicación (App Keys) a su cuenta de Betfair.

Una clave de aplicación ‘en directo’ y una ‘retardada’. Una clave de aplicación retardada se muestra como ‘Version 1.0-DELAY’ a través de createDeveloperAppKeys/getDeveloperAppKeys

- En el momento de su creación, la clave de la aplicación en directo estará inactiva.
- Para solicitar una clave de aplicación en directo, haga clic aquí y seleccione Exchange API > For My Personal Betting (API de Exchange > Para mis apuestas personales) y complete el formulario de solicitud en la parte inferior de la página. Se aplica una tarifa de activación única de £299; la cuál se retirará directamente de su cuenta de Betfair una vez que se apruebe el acceso
La clave de aplicación retardada funciona en el Exchange (Intercambio) de Betfair en directo y no en el entorno de testbed/sandbox.
- La clave de aplicación retardada se debe utilizar para fines de desarrollo y pruebas funcionales, y proporciona datos de precios de Betfair retardados (EX_BEST_OFFERS solamente). La demora varía entre de 1 y 60 segundos.
- La clave de aplicación retardada también se debe utilizar en aplicaciones de simulación/práctica donde no está disponible la opción para apostar en mercados de Betfair en directo.
La clave de aplicación retardada no devuelve los datos del volumen de transacción 'totalMatched' o EX_ALL_OFFERS a través de tlistMarketBook. La API de secuencia solo está disponible a través de la clave de aplicación en directo sujeta a aprobación.

* Los datos históricos además están disponibles para realizar pruebas y análisis. Consulte el directorio de aplicación para obtener más información sobre estos servicios.

Acceso a apuestas personales. Descripción general de la clave de aplicación

Consulte la tabla siguiente para ver un resumen de los datos o servicios disponibles para las claves de aplicación retardada y 
en directo.


### Administración de inicio de sesión

Inicio de sesión
Inicio de sesión no interactivo
Inicio de sesión interactivo
Inicio de sesión interactivo: aplicación de escritorio
Inicio de sesión interactivo: método de API
Límites de solicitud de inicio de sesión
Mantener activa
Encabezados
Definición de URL
Estructura de respuesta
Valores de estado
Valores de error Ejemplo de llamada
Mantener activa con éxito
Cierre de sesión
Definición de URL
Encabezados
Estructura de respuesta
Valores de estado
Valores de error
Ejemplo de llamada
Preguntas frecuentes del inicio de sesión
¿Cuándo debo utilizar el inicio de sesión no interactivo?
¿Por qué se requiere la redirección de URL para el inicio de sesión interactivo?
¿Por qué no existe un extremo no interactivo que acepte solo un nombre de usuario y una contraseña?
¿Por qué se termina mi tiempo de la sesión, a pesar de que he estado recuperando precios?
¿Por qué mi solicitud de inicio/cierre de sesión interactivo me da el error errorCode=FORBIDDEN?

Inicio de sesión

La API de Betfair ofrece tres flujos de inicio de sesión para desarrolladores, según el caso de uso de su aplicación:


Inicio de sesión no interactivo

Si está creando una aplicación que se ejecutará de manera autónoma, hay un flujo de inicio de sesión separado que debe seguir para asegurarse de que su cuenta permanezca segura.


Inicio de sesión interactivo

Si está creando una aplicación que se usará de forma interactiva, este es el flujo para usted. Este flujo tiene dos variantes:

Inicio de sesión interactivo: aplicación de escritorio

Este flujo de inicio de sesión usa las páginas de inicio de sesión de Betfair y permite que su aplicación maneje adecuadamente todos los errores y las redirecciones de la misma manera que el sitio web de Betfair

Inicio de sesión interactivo: método de API

Este flujo usa un extremo de API de JSON y es la forma más sencilla de empezar si desea crear su propio formulario de inicio de sesión.


Límites de solicitud de inicio de sesión




Mantener activa

Puede utilizar Mantener activa para extender el período de espera de la sesión. El tiempo de sesión mínimo actualmente es de 20 minutos (Exchange [Intercambio] italiano). En el Exchange (Intercambio) internacional (.com) el tiempo de la sesión actual es de 4 horas. Por lo tanto, debe solicitar la opción Mantener activa dentro de este tiempo para evitar la expiración de la sesión. Si no recurre a la opción Mantener activa dentro del período especificado, la sesión expirará. Tenga en cuenta lo siguiente: Los tiempos de sesión no se determinan ni extienden según la actividad de la API.

Encabezados




Definición de URL

Jurisdicciones internacionales:





Jurisdicción española




Jurisdicción rumana
https://identitysso.betfair.ro/api/keepAlive


Parámetros: ninguno


Estructura de respuesta




Valores de estado





Valores de error





Ejemplo de llamada








Mantener activa con éxito





Cierre de sesión
Puede usar Logout (Cerrar sesión) para terminar su sesión existente.


Definición de URL

https://identitysso.betfair.com/api/logout

La presencia del encabezado “Aceptar: aplicación/json” indicará que el servicio debe responder con JSON y no una página HTML


Encabezados



Estructura de respuesta





Valores de estado





Valores de error





Ejemplo de llamada





Preguntas frecuentes del inicio de sesión

¿Cuándo debo utilizar el inicio de sesión no interactivo?

Debe utilizar el inicio de sesión no interactivo cuando el usuario no esté presente para iniciar sesión en la aplicación. Un ejemplo de esto es un robot automatizado que podría necesitar iniciar sesión sin que el usuario active un inicio de sesión. Las interfaces de terceros de Betfair, utilizadas por varios usuarios, y que actúan como un proxy directo de una solicitud del usuario deben utilizar el inicio de sesión interactivo en su lugar.

¿Por qué se requiere la redirección de URL para el inicio de sesión interactivo?

La redirección de URL es necesaria para publicar el token de sesión en la aplicación al final del proceso de inicio de sesión. Para obtener más información acerca de cómo manejar el token de sesión, consulte Inicio de sesión interactivo desde un escritorio

¿Por qué no existe un extremo no interactivo que acepte solo un nombre de usuario y una contraseña?

Betfair toma muy en serio la seguridad del usuario y ha hecho muchas mejoras en el proceso de inicio de sesión junto con cambios adicionales que se han hecho a petición de algunos de nuestros reguladores. Esto significa que no puede confiar en un nombre de usuario y una contraseña como la única información que pueda ser necesaria en el inicio de sesión. Algunos ejemplos de flujos de trabajo que se usan actualmente son los códigos de autorización de 2 factores, identificadores nacionales y adicionales para una región o solicitudes de información adicional de la cuenta o migración de la cuenta.

¿Por qué se termina mi tiempo de la sesión, a pesar de que he estado recuperando precios?

Por razones de seguridad, necesitamos que la aplicación que usa la API solicite explícitamente la operación Mantener activa no más de una vez cada 4 horas en respuesta a la actividad del usuario. En el caso de aplicaciones no interactivas, se debe solicitar la operación para mantener activa cada 4 horas mientras está activa.

¿Por qué mi solicitud de inicio/cierre de sesión interactivo me da el error errorCode=FORBIDDEN?

La clave de aplicación no está usando la URL de redirección correcta. Solo de forma predeterminada se admitirá Https://www.betfair.com como la URL de redirección.

Inicio de sesión no interactivo (robot)

Inicio
Creación de un certificado autofirmado
Vinculación del certificado con su cuenta de Betfair
Nota sobre los formatos de archivo
Detalles de una solicitud de inicio de sesión
Certificado los detalles de la interfaz de inicio de sesión
Definición de URL
Encabezados de solicitud
Parámetros de solicitud
Respuesta
Código de ejemplo para inicio de sesión no interactivo
Muestra el código C# con la tienda de claves PKCS#12
Ejemplo de código Java que usa la biblioteca de cliente Apache http y la tienda de claves PKCS#12
Ejemplo de código Python


El método de inicio de sesión no interactivo para API-NG requiere crear y cargar un certificado autofirmado que se utilizará, junto con su nombre de usuario y contraseña, para autenticar sus credenciales y generar un token de sesión.

Para los fines de esta guía, hemos utilizado openssl para generar este cliente, cuyos detalles pueden encontrarse en http://www.openssl.org/


Inicio

Hay un par de pasos necesarios antes de que podamos iniciar sesión:

Cree un certificado autofirmado
Vincule el certificado con su cuenta de Betfair


Creación de un certificado autofirmado

API-NG requiere que se use un certificado RSA de 1024 bits o 2048 bits. Hay varios tutoriales disponibles en Internet, pero tenga en cuenta que el certificado debe ser para la autenticación del cliente (la mayoría de los tutoriales solo cubre la autenticación del servidor).


Cree un par de claves RSA pública/privada utilizando openssl



Actualice o cree el archivo de configuración de openssl (openssl.cnf) para OpenSSL con el fin de reemplazar algunos de los ajustes predeterminados:





Cree una solicitud de firma de certificado (CSR).



Autofirme la solicitud de certificado para crear un certificado






Vinculación del certificado con su cuenta de Betfair

Los pasos anteriores deben haber creado los siguientes archivos:


Antes de que inicie sesión utilizando el certificado, este se debe conectar con su cuenta de Betfair, de esta manera:


Inicie sesión en su cuenta de Betfair mediante betfair.com. Pegue la siguiente URL en la barra de direcciones de su navegador
Desplácese hasta https://myaccount.betfair.com/accountdetails/mysecurity?showAPI=1. Nota: Utilice https://myaccount.betfair.it/accoun tdetails/mysecurity?showAPI=1 para el Exchange (Intercambio) italiano o el extremo relevante para su propia jurisdicción. Consulte la sección de Definición de URL para obtener más detalles
Desplácese hasta la sección titulada “Automated Betting Program Access” (Acceso al programa de apuesta automatizado) y haga clic en ‘Edit’ (Editar)
Haga clic en “Browse” (Examinar) y, a continuación, busque y seleccione el archivo client-2048.crt (client-2048.pem si corresponde) creado anteriormente.
Haga clic en el botón “Upload Certificate” (Cargar certificado).

Desplácese hacia abajo hasta la sección “Automated Betting Program Access” (Acceso al programa de apuesta automatizado) si es necesario y deben aparecer los detalles del certificado. Ahora debe poder iniciar sesión en su cuenta de Betfair mediante el extremo de API-NG.

Nota sobre los formatos de archivo

Algunos sistemas requieren que los certificados de cliente se encuentren en un formato diferente del que hemos creado. Los dos formatos más comunes son: a) certificado y clave en formato PEM en un archivo único y b) Archivo en formato PKCS#12. Las aplicaciones .NET requieren un archivo en formato PKCS#12.

Para crear un archivo de formato PEM que contenga tanto la clave privada como el certificado, puede utilizar el siguiente comando:


Cree el formato PKCS#12 con crt y la clave





Detalles de una solicitud de inicio de sesión

Una solicitud de inicio de sesión ahora puede realizarse de la siguiente manera:

Envíe una solicitud de “ENVÍO” de HTTP: https://identitysso.betfair.com/api/certlogin
Como parte de la conexión SSL, se debe entregar el certificado creado anteriormente.
Incluya un encabezado personalizado llamado “X-Application” con un valor que identifique su aplicación. El valor no está validado y solo se utiliza para ayudar a solucionar problemas y diagnosticar cualquier problema.
Asegúrese de que tipo de contenido del ENVÍO sea “application/x-www-form-urlencoded” en lugar de un adjunto MIME codificado.
Como parte del cuerpo del ENVÍO, incluya dos parámetros “nombre de usuario” y “contraseña” que deben tener el correspondiente nombre de usuario/contraseña de su cuenta.
Certificado los detalles de la interfaz de inicio de sesión

Definición de URL

Este extremo también está disponible aquí:

identitysso.betfair.com
identitysso.betfair.es
identitysso.betfair.it
idenititysso.betfair.ro
identitysso.w-con.betfair.com
identitysso.betfaironline.eu



Encabezados de solicitud

X-Application: debe establecer el encabezado de X-Application para su clave de aplicación.

Parámetros de solicitud

Nombre de usuario (obligatorio): el nombre de usuario del usuario que inicia sesión.

Contraseña (obligatorio): la contraseña del usuario que inicia sesión.



Respuesta

La respuesta devuelta es una cadena json. Si la respuesta es correcta, entonces la clave de loginStatus contendrá SUCCESS (Éxito), por ejemplo:



Si se devuelve un error o excepción, la respuesta será estructurada de la siguiente manera y loginStatus contendrá un motivo del error:




Los posibles códigos de retorno de error y excepción son:


Comando curl de ejemplo para comprobar rápidamente el inicio de sesión basado en el certificado



Código de ejemplo para inicio de sesión no interactivo

Prueba el código C# utilizando la clave PKCS#12

Consulte el código de ejemplo a través de https://github.com/betfair/API-NG-sample-code/tree/master/loginCode/Non-interactive-cSharp

Prueba el código Java que usa la biblioteca de cliente Apache http y la tienda de claves PKCS#12


Ejemplo de código Python




El inicio de sesión interactivo: aplicación de escritorio


Descripción general
Obtención de sessionToken desde los datos de ENVÍO
Definición de URL (Global)
Definición de URL: otras jurisdicciones
Parámetros


Descripción general

El inicio de sesión interactivo se utiliza cuando el usuario está presente para iniciar la sesión (por ejemplo, aplicaciones de escritorio de terceros) y gestionará toda la información adicional necesaria en el inicio de sesión, según la cuenta de un cliente (como códigos de autenticación de 2 factores o identificadores nacionales).

Esto se logra mediante la integración de la página de inicio de sesión de Betfair IdentitySSO en su aplicación y, a continuación, la obtención de un token de sesión exitoso al iniciar sesión. La operación Mantener activa se debe solicitar dentro del tiempo de caducidad de sesión si el usuario sigue utilizando activamente su aplicación. La página de inicio de sesión integrada inicialmente es así:




La secuencia de inicio de sesión interactivo es así:



Obtención de sessionToken desde los datos de ENVÍO

Una vez que se ha iniciado correctamente una sesión, el Javascript de la página ENVIARÁ el token de sesión (ssoid) a la URL proporcionada como URL de redirección. Para una aplicación de escritorio, no es necesario que sea una página real, ya que la aplicación de escritorio puede interceptar la solicitud de ENVÍO como sucede a través del contenedor del navegador integrado. Una aplicación basada en Windows puede integrar un navegador web en la aplicación y utilizar el evento BeforeNavigate2 para capturar los datos del envío dirigidos a la URL de redirección, allí existen alternativas específicas de la plataforma. El cuerpo de la solicitud de ENVÍO contendrá dos parámetros codificados de URL (que necesitará para decodificar la URL):

ssoid: este es el token de sesión y deberá adjuntarse a las solicitudes hechas a API-NG en el encabezado X-Authentication.
errorCode: esto lo devuelve Betfair en una URL y proporciona el motivo del error de inicio de sesión.



El inicio de sesión interactivo es el mismo flujo inicio de sesión utilizado por el sitio web de Betfair y, por lo tanto, cualquier mensaje será devuelto directamente por Betfair y tratado de la misma manera.


Definición de URL (Global)



Definición de URL: otras jurisdicciones

Usuarios de la jurisdicción australiana:



Usuarios de la jurisdicción italiana:


Usuarios de la jurisdicción española:


Usuarios de la jurisdicción rumana:

Parámetros



Inicio de sesión interactivo: extremo de API

Descripción general y limitaciones
Definición de URL (Global)
Otras jurisdicciones
Parámetros (ENVÍO)
Encabezados
Ejemplo de ENVÍO
Carga
Ejemplo de activación de curl
Ejemplo de inicio de sesión exitoso:
Estructura de respuesta
Valores de estado
Códigos de estado y valores de error
Posibles códigos de retorno de error y excepción


Descripción general y limitaciones

El extremo de inicio de sesión de API es el método más sencillo de integración para la mayoría de las aplicaciones en cuanto al tiempo de desarrollo esperado, pero es a costa de ser menos flexible para casos límite que la página de inicio de sesión incorporada de Betfair. Permitirá que el usuario proporcione un nombre de usuario y una contraseña o un nombre de usuario y (contraseña + código de autenticación de 2 factores) si tiene habilitada una autenticación fuerte.

Se recomienda encarecidamente a los clientes con robots que escriben para su propio uso, emplear el extremo no interactivo con un certificado SSL.
Recomendamos que las aplicaciones de terceros que estarán expuestas a una amplia gama de usuarios utilicen el método de inicio de sesión interactivo de incorporar la página de inicio de sesión incorporada de Betfair, ya que esto permite que su aplicación maneje flujos de trabajo adicionales, como las actualizaciones de los términos y condiciones, así como los identificadores adicionales específicos y jurisdiccionales.

Los métodos de Mantener activa y cerrar sesión siguen siendo los mismos con este método de inicio de sesión.

Definición de URL (Global)


Otras jurisdicciones

Usuarios de la jurisdicción italiana:


Usuarios de la jurisdicción española:


Usuarios de la jurisdicción rumana:


Parámetros (ENVÍO)







Encabezados


La presencia de “Accept: application/json” indicará a SSO que se debe responder con JSON y no una página HTML.

Ejemplo de ENVÍO

Accept: application/json
X-Application: <AppKey>
Tipo de contenido: application/x-www-form-urlencoded
Extremo de URL: https://identitysso.betfair.com/api/login

Carga

nombre de usuario=usuario&contraseña=contraseña.

Ejemplo de activación de curl



Ejemplo de inicio de sesión exitoso:



Estructura de respuesta

Valores de estado



Códigos de estado y valores de error

A continuación, se describen los códigos de estado que pueden ser devueltos y los correspondientes valores de error:


LIMITED_ACCESS: acceso limitado (por ejemplo, se puede iniciar sesión en las cuentas, pero no se puede apostar debido a una suspensión de la cuenta), se proporcionará la sesión del producto.



LOGIN_RESTRICTED: el inicio de sesión está restringido (en caso de punto de direccionamiento indirecto, esto es lo que se devolverá), no se proporcionará la sesión del producto:


FAIL: todos los otros casos se consideran errores, no se proporcionará la sesión del producto:







Posibles códigos de retorno de error y excepción


### Mejores prácticas

Desarrollo y prueba
Gestión de sesiones
Encabezado Expectativa: 100: continuar
Habilitación de la compresión HTTP
Conexión persistente de HTTP
Otras sugerencias de rendimiento

Para optimizar el rendimiento y asegurarse de que su aplicación esté interactuando con la API de Betfair correctamente y de la forma más eficiente posible, recomendamos encarecidamente seguir las directrices de mejores prácticas a continuación.

Desarrollo y prueba

Debe utilizar la clave de aplicación retardada para cualquier desarrollo inicial y prueba funcional. Solo se aplica para el acceso de la clave de aplicación en directo una vez que esté listo para empezar a realizar la transacción en Exchange utilizando su clave de aplicación en directo.

Consulte la descripción general del acceso a apuestas personales para obtener más detalles sobre la diferencia entre las claves de aplicación retardadas y en directo

Gestión de sesiones

Use el Inicio de sesión para crear una nueva sesión y la operación Mantener activa para prolongar la sesión más allá del tiempo de caducidad establecido de la sesión. Una sola sesión se puede utilizar en varios subprocesos/llamadas de API simultáneamente.

Debe asegurarse de manejar el error INVALID_SESSION_TOKEN dentro del código al crear un nuevo token de sesión a través del método Inicio de sesión de API.

Encabezado Expectativa: 100: continuar

Debe tener en cuenta que si usa .NET Framework, deberá establecer la propiedad pertinente en ServicePointManager, lo que impide que se agregue el encabezado “Expectativa”:

System.Net.ServicePointManager.Expect100Continue = false;

Habilitación de la compresión HTTP

La compresión de HTTP es una capacidad integrada en los servidores web y los clientes web para reducir el número de bytes transmitidos en una respuesta HTTP. Esto hace un mejor uso del ancho de banda disponible y aumenta el rendimiento mientras reduce el tiempo de descarga. Cuando está habilitada, los datos del protocolo HTTP se comprimen antes de que se envíen desde el servidor. Los clientes que pueden recibir datos de HTTP comprimido avisan que admiten la compresión en el encabezado HTTP. Casi todos los navegadores web modernos admiten la compresión HTTP de manera predeterminada.

La API de Betfair utiliza HTTP para manejar la comunicación entre los servidores y clientes de API. Por lo tanto, los mensajes JSON se pueden comprimir utilizando la misma compresión HTTP utilizada por los navegadores web. Las aplicaciones API personalizadas pueden requerir alguna modificación antes de que puedan aprovechar esta característica. En concreto, necesitan enviar un encabezado HTTP adicional para indicar que admiten la recepción de respuestas comprimidas de la API. Además, algunos entornos requieren descomprimir explícitamente la respuesta.

Por consiguiente, recomendamos que toda solicitud de API de Betfair se envíe con el encabezado de solicitud ‘Accept-Encoding: gzip, deflate’.

Conexión persistente de HTTP

Recomendamos que el encabezado Conexión: mantener activa esté configurado para todas las solicitudes con el fin de garantizar una conexión persistente y, por lo tanto, reduzca la latencia.

Otras sugerencias de rendimiento


Se pueden encontrar consejos adicionales sobre optimización de rendimiento de HTTPClient en http://hc.apache.org/httpclient-3.x/performance.html
### Herramientas de demostración de API

Las herramientas de demostración están disponibles para API-NG tanto para la API de apuestas como para la de cuentas. Las herramientas de demostración las pueden utilizar los desarrolladores para permitir una rápida experimentación con la API.




Obtención de un token de sesión para las herramientas de demostración

Hay varias maneras en que puede obtener un token de sesión para el visualizador:

Use el token de sesión completado previamente desde el sitio web

Las herramientas de demostración completarán el campo de token de sesión con el valor de un token de sesión que se encuentre en la tienda de cookies del navegador para el sitio web Betfair.com. Inicie sesión en www.betfair.com (con una ficha separada del navegador) y actualice la página de herramientas de demostración para que introduzca automáticamente el campo Token de sesión

Agregue manualmente el ssoid (token de sesión) desde la cookie del sitio web.

Con Google Chrome, puede inspeccionar y copiar la sesión directamente desde el navegador haciendo lo siguiente:

1.	Presione Ctrl+Mayús+J
Recurso de selección > Cookies > www.betfair.com
Copie el valor de la cookie con el nombre ssoid y péguelo en la herramienta de demostración

3.	Use el ejemplo de inicio de sesión interactivo de API-NG

Descargue SampleAPI.exe, que es una versión compilada del código de inicio de sesión interactivo de ejemplo que se describe en la documentación aquí, con la fuente de API-NG Sample code github repo.

Introduzca su clave de aplicación y siga las instrucciones de inicio de sesión; se extraerá el token de su sesión y se le presentará a través de la aplicación.


### Límites de solicitud de datos de mercado


Aunque puede solicitar múltiples mercados de listMarketBook, listMarketCatalogue y listMarketProfitandLoss, existen límites en la cantidad de datos pedidos en una sola solicitud.


En las tablas siguientes, se explica el “peso” de los datos para cada MarketProjection o PriceProjection. Si supera el peso máximo de 200 puntos, la API mostrará el error TOO_MUCH_DATA.
listMarketCatalogue


listMarketBook


Nota: las combinaciones específicas de priceProjections tendrán diferentes pesos que no son la suma de los pesos individuales. Consulte un resumen de esto a continuación:


Si se utiliza exBestOffersOverrides, el peso se calcula por peso * (requestedDepth/3).

listMarketProfitandLoss


### Comprensión de la navegación del mercado


En API-NG, los mercados de navegación utilizan los conceptos de búsqueda facetada. Probablemente haya visto el uso de búsquedas facetadas en sitios como eBay o Amazon, donde tiene que elegir una categoría, por ejemplo “Zapatos”, y, a continuación, ve una lista de zapatos. Luego, puede limitar la búsqueda por facetas. Por ejemplo, por color o precio. De manera similar, las nuevas API de deportes permiten encontrar mercados que le interesen y, a continuación, obtener datos acerca de una faceta de esos mercados.

La forma de pensar de las operaciones de navegación de la API es imaginar una sola tabla que enumere cada mercado, junto con diversos metadatos sobre el mercado. Las columnas de la tabla son las facetas (y las operaciones de navegación en API devuelven algunas de ellas en combinación):



Como puede ver, la tabla tiene cuatro mercados junto con algunos de los metadatos asociados con ese mercado. Por supuesto, la tabla real tendría decenas de miles de mercados y más columnas.

En la parte superior, se pueden ver tres de las operaciones de navegación. Cada una de estas operaciones tiene un "MarketFilter". MarketFilter filtra la tabla de mercados y selecciona a los que coinciden. MarketFilter puede contener cosas, como “vamos a jugar” o “eventId 7”, etc. Si activa “listCompetitions” y pasa por un filtro que se parece a:
Code:

{ "filter": {"turnsInPlay" : true }}

Los mercados seleccionados serían así:



En el ejemplo, los mercados 1001, 2355 y 5621 son los que coinciden con el filtro. Cuando llama a “listCompetitions” con ese filtro, los datos devueltos son las columnas que contienen información sobre la competencia:


En este ejemplo, obtendrá una lista de competencias como:

Code:

{"competitionId" : "23", "competitionName" : "World Cup 2013"}

Observe que no apareció la competencia “Final 2013”. Esto se debe a que el mercado no fue seleccionado por el MarketFilter. Asimismo, tenga en cuenta que aunque el mercado de 2355 fue seleccionado por MarketFilter, no está asociado con una competencia; por lo tanto, no se devolvió ningún nombre ni ID de competencia para ese mercado.
Como otro ejemplo, supongamos que utiliza el mismo MarketFilter que antes mientras llama a listEvents. En ese caso, los datos devueltos son las columnas que contengan eventId y eventName para los mercados que coincidan con el filtro (es decir, turnsInPlay = True):



En este ejemplo, obtendrá una lista de eventos como:

Code:

[{"eventId" : "24", "eventName" : "Arsenal Vs. Reading"}, {"eventId" : "124", "eventName" : "Ascot 16th September"}, {"eventId" : "23", "eventName" : "Cheltenham 17th September"}]

Nuevamente, observe que el evento “Celtics vs. Nicks" no fue devuelto porque no fue seleccionado por el MarketFilter.

Un ejemplo más. Supongamos que solo estaba interesado en mercados de línea y desea encontrar todos los deportes (EventTypes) que contengan mercados de línea. Debería crear un MarketFilter como este:

Code:

{ "filter": {"MarketBettingType" : "LINE" }}

Y llame a listEventTypes con ese filtro. Los mercados seleccionados por ese MarketFilter serían:


y los datos devueltos serían:


Code:

{"eventTypeId" : "4", "EventTypeName" : "Basketball"}

Al usar el conjunto de operaciones de exploración, puede crear fácilmente un árbol de menús de los mercados en cualquier jerarquía que desee. Puede seleccionar listEventTypes para obtener los deportes en la parte superior del menú. O, podría llamar a "listCountries" y utilizar los mercados en un país como la raíz del árbol.

También está listMarketCatalogue, por lo tanto, si no te interesa crear una navegación visual, simplemente puede llamar a listMarketCatalogue con un MarketF ilter que defina los mercados que le interesan y obtener información acerca de los mercados.
## Guía de referencia

- Datos de navegación para las aplicaciones
- API de apuestas
- Operaciones de apuestas
listCompetitions
listCountries
listCurrentOrders
listClearedOrders
listClearedOrders: campos de acumulación disponibles
listEvents
listEventTypes
listMarketBook
listRunnerBook
listMarketCatalogue
listMarketProfitAndLoss
listMarketTypes
listTimeRanges listVenues
placeOrders
cancelOrders
replaceOrders
updateOrders
Apuesta de precio inicial de Betfair (BSP)
Apuestas en el Exchange (Intercambio) italiano
Apuestas en el Exchange (Intercambio) español
Excepciones de apuestas
Enumeraciones de apuestas
Definiciones de tipo de apuestas
API de cuentas
Operaciones de cuentas
createDeveloperAppKeys
getAccountDetails
getAccountFunds
getDeveloperAppKeys
getAccountStatement
listCurrencyRates
transferFunds
Excepciones de cuentas
Enumeraciones de cuentas
TypeDefinitions de cuentas
activateApplicationSubscription
cancelApplicationSubscription
getAffiliateRelation
getApplicationSubscriptionHistory
getApplicationSubscriptionToken
getVendorClientId
getVendorDetails
isAccountSubscribedToWebApp
listAccountSubscriptionTokens
listApplicationSubscriptionTokens
revokeAccessToWebApp
token
updateApplicationSubscription
API de pulso
API de estado de carrera
Servicios de proveedor en API-NG
Documentos de definición de interfaz
Guía de referencia (copia sin conexión)

Versiones de la documentación

El registro a continuación detalla las principales actualizaciones de la Guía de referencia de API-NG.



### Datos de navegación para las aplicaciones

Extremo y encabezados necesarios
EjemploEjemplo Solicitud
Configuraciones regionales admitidas
Estructura del archivo de datos de navegación
Estructura de modelo de JSON
ROOT
EVENT_TYPE
GROUP
EVENT
RACE
MARKET

Extremo y encabezados necesarios

Este servicio de Datos de navegación para aplicaciones permite la recuperación del menú completo de navegación del mercado de Betfair desde un archivo comprimido.




Se requieren los siguientes encabezados de solicitud:

- X-Application: la clave de la aplicación.
- X-Authentication: su token de sesión, obtenido a partir de la respuesta de inicio de sesión de API.


Solicitud de ejemplo



Configuraciones regionales admitidas

Los siguientes idiomas están admitidos por el archivo de navegación:

en | en_GB | bg | da | de | el | es | it | pt | ru | sv

Inglés: en
Español: es
Italiano: it
Alemán: de
Sueco: sv
Portugués: pt
Ruso: ru
Griego: el
Búlgaro: bg
Danés: da

Estructura del archivo de datos de navegación

Este es un diagrama que muestra cómo está estructurado el archivo de datos de navegación.








En inglés claro:

Un nodo de grupo ROOT tiene uno o muchos nodos de EVENT_TYPE

Un nodo de EVENT_TYPE tiene cero, uno o muchos nodos de GROUP

Un nodo de EVENT_TYPE tiene cero, uno o muchos nodos de EVENT

Un nodo de EVENT_TYPE de carreras de caballos tiene cero, uno o muchos nodos de RACE

Un nodo de RACE tiene uno o muchos nodos de MARKET

Un nodo de GROUP tiene cero, uno o muchos nodos de EVENT

Un nodo de GROUP tiene cero, uno o muchos nodos de GROUP

Un nodo de EVENT tiene cero, uno o muchos nodos de MARKET

Un nodo de EVENT tiene cero, uno o muchos nodos de GROUP

Un nodo de EVENT tiene cero, uno o muchos nodos de EVENT

Estructura de modelo de JSON

ROOT


EVENT_TYPE


GROUP


EVENT



RACE



MARKET



### API de apuestas


Extremos

Busque los detalles de los extremos de la API de apuestas actual. Si tiene una cuenta de Exchange (Intercambio) española o italiana, vea más detalles a través de los siguientes enlaces:

Exchange (Intercambio) global



- Apuestas en el Exchange (Intercambio) español
- Apuestas en el Exchange (Intercambio) italiano

Operaciones de apuestas


Resumen de la operación





listCompetitions

Operación



listCountries

Operación

listCurrentOrders

Operación



listClearedOrders


Operación




listClearedOrders: campos de acumulación disponibles

La tabla siguiente indica los campos que estarán disponibles en cada acumulación al realizar solicitudes a listClearedOrders utilizando el parámetro groupBy.



listEvents


Operación

















listEventTypes

Operación


listMarketBook

Operación



Apuestas virtuales

El Exchange de Betfair utiliza un algoritmo de ‘incidencia cruzada’ para mostrar los mejores precios posibles (apuestas) disponibles al tener en cuenta las ofertas a favor y en contra (apuestas sin coincidencias) en todas las selecciones.





Una de las formas más fáciles para comprender cómo se generan las apuestas virtuales para la coincidencia cruzada es analizando un par de ejemplos.


Considere el siguiente mercado y qué pasaría si hacemos una gran apuesta a favor del empate a 1,01:





Sin una coincidencia cruzada, esta apuesta coincidiría en tres partes:

1) £150 a 5,0,
2) £250 a 3,0,
y £999 a 1,01 con todo lo demás que quede sin coincidencia.

Con la coincidencia cruzada podemos hacer algo mejor.

Tenemos una apuesta a favor de Newcastle por £120 a 2,0 y una apuesta a favor de Chelsea por £150 a 3,0 (se muestra en rosa la parte disponible para apostar en contra del mercado).



Estas dos apuestas pueden coincidir con una apuesta a favor del empate a un precio de 6,0 ya que 2,0, 3,0 y 6,0 forman una reserva del 100 %. Para asegurarnos de que la reserva sea equilibrada, elegimos que las apuestas sean inversamente proporcionales a los precios.

Esto significa que tomamos los £120 a 2,0 en Newcastle, solo £80 a 3,0 en Chelsea y £40 a 6,0 en el empate, que es la primera apuesta virtual.

Ahora tenemos una apuesta a favor de Newcastle por £75 a 2,5 y una apuesta a favor de Chelsea por £70 a 3,0 (de nuevo se muestra en rosa la parte disponible para apostar en contra del mercado).

Estas dos apuestas pueden coincidir con una apuesta a favor del empate a un precio de 3,75 ya que 2,5, 3,0 y 3,75 también forman una reserva del 100 %.

Equilibrar las apuestas significa que tomamos los £75 a 2,5 en Newcastle, solo £62.5 a 3,0 en Chelsea y £50 a 3,75 en el empate, que es la segunda apuesta virtual. Debido a que 3,75 es menor que 5,0, el valor de £150 a 5,0 sería la primera coincidencia seguida por £50 a 3,75. Si continuáramos con este proceso, obtendríamos mayor coincidencias a 1,50 y 1,05, pero para poder mostrar la visión del mercado, tenemos los mejores 3 precios para las apuestas a favor disponibles en el empate, y así podemos dejar de calcular las apuestas virtuales. Las apuestas virtuales son las apuestas que habrían coincidido si hubiéramos recibido una apuesta lo suficientemente grande a favor a 1,01; en este ejemplo, £40 a 6,0 y £50 a 3,75. Tomamos estas apuestas virtuales y las combinamos con las apuestas existentes en el mercado para generar la siguiente visión de mercado (con las apuestas virtuales en verde).



Se repite el proceso para obtener las apuestas virtuales en contra (apuestas a favor disponibles) de Newcastle y Chelsea.

Aquí tenemos un mercado ligeramente diferente (como antes, elegido para que los números sean fáciles), considere qué pasaría si hiciéramos una gran apuesta en contra a 1000 en el empate.



Sin la coincidencia cruzada, esta apuesta coincidiría con tres partes: 1) £100 a 10,0, 2) £50 a 50,0 y £2 a 1000 con todo lo demás que quede sin coincidencia. Con la coincidencia cruzada podemos hacer algo mejor. Tenemos una apuesta en contra de Newcastle por £300 a 2,0 y una apuesta en contra de Chelsea por £150 a 3,0 (se muestra en azul la parte disponible para apostar a favor del mercado). Estas dos apuestas pueden coincidir con una apuesta en contra del empate a un precio de 6,0 ya que 2,0, 3,0 y 6,0 forman una reserva del 100 %. Para asegurarnos de que la reserva sea equilibrada, elegimos que las apuestas sean inversamente proporcionales a los precios. Esto significa que tomamos solo £225 a 2,0 en Newcastle, £150 a 3,0 en Chelsea y £75 a 6,0 en el empate, que es la primera apuesta virtual.

Si suponemos que estas apuestas dieron coincidencias, el mercado sería así:



Tenemos una apuesta en contra de Newcastle por £75 a 2,0 y una apuesta en contra de Chelsea por £250 a 2,4 (se muestra en azul la parte disponible para apostar a favor del mercado). Estas dos apuestas pueden coincidir con una apuesta en contra del empate a un precio de 12,0 ya que 2,0, 2,4 y 12,0 también forman una reserva del 100 %.
Equilibrar las apuestas significa que tomamos los £75 a 2,0 en Newcastle, solo £62.5 a 2,4 en Chelsea y £12,50 a 12,0 en el empate, que es la segunda apuesta virtual.

Esto genera el siguiente mercado:



Esta vez no podemos continuar el proceso porque no hay un precio válido para una apuesta virtual al empate que resulte en una reserva del 100 %, por lo que podemos detener el cálculo de las apuestas virtuales. Nuevamente, las apuestas virtuales son las apuestas que habrían coincidido si hubiéramos recibido una apuesta lo suficientemente grande en contra a 1000; en este ejemplo, £75 a 6,0 y £12.50 a 12,0. Tomamos estas apuestas virtuales y las combinamos con las apuestas existentes en el mercado para generar la siguiente visión de mercado (con las apuestas virtuales en naranja).



listRunnerBook

Lista<MarketBook> listRunnerBook ( MarketId marketId, SelectionId selectionId, double handicap, PriceProjection priceProjection, OrderProj ection orderProjection, MatchProjection matchProjection, boolean includeOverallPosition, boolean partitionMatchedByStrategyRef, Set<String> customerStrategyRefs, StringcurrencyCode,Stringlocale, Date matchedSince, Set<BetId> betIds) muestra APINGException

Devuelve una lista de los datos dinámicos sobre un mercado y un corredor especificado. Los datos dinámicos incluyen los precios, la situación del mercado, el estado de selecciones, el volumen negociado y el estado de los pedidos que haya realizado en el mercado.






Desde 1.0.0

listMarketCatalogue

Operación

Descripción de RUNNER_METADATA

La RUNNER_METADATA que devuelve listMarketCatalogue para las Carreras de caballos (cuando está disponible) se describe en la siguiente tabla.



listMarketProfitAndLoss


listMarketTypes

Operación















listTimeRanges

Operación


listVenues

Operación

placeOrders

- Operación
- Cómo hacer una apuesta
- Cómo hacer una apuesta de Betfair SP
- Apuestas de ejecución inmediata
- Ejemplos
- Parámetro de versión del mercado
- Apuesta al pago o ganancia/riesgo
- Ejemplos
- Capacidad para hacer apuestas mínimas a mayores precios
- Apuesta Each Way
- Incrementos de precios de Betfair
- Parámetros de moneda

Operación

















Cómo hacer una apuesta

Para hacer una apuesta, se requieren los parámetros de marketId y selectionId de la llamada de API listMarketCatalogue. Los siguientes parámetros harán una apuesta de Exchange (Intercambio) normal en las probabilidades de 3 para una apuesta de £2,0.

Si la apuesta se hace correctamente, se devuelve un betId en la respuesta de placeOrders

Solicitud de placeOrders




Respuesta de placeOrder



Cómo hacer una apuesta de Betfair SP

Para hacer una apuesta en una selección en Betfair SP, debe especificar los siguientes parámetros en la solicitud de placeOrders. El siguiente ejemplo haría una apuesta a favor de Betfair SP en la selección requerida para una apuesta de £2,00.


Solicitud de placeOrders




Respuesta de placeOrders



Apuestas de ejecución inmediata

Al establecer el parámetro opcional ‘TimeInForce’ en un envío de limitOrder con un valor ‘FILL_OR_KILL’ y opcionalmente pasar un valor minFillSize, el Exchange (Intercambio) solo coincidirá con el pedido si, al menos, lo puede hacer con el minFillSize especificado (si se pasó) o con todo el pedido (si no). Cualquier pedido que no coincida y cualquier parte del pedido que quede sin coincidencia (si se especifica minFillSize) se cancelará inmediatamente.

Tenga en cuenta lo siguiente: El algoritmo de coincidencia para los pedidos de ejecución inmediata se comporta de forma ligeramente diferente a los pedidos límite estándares. Mientras que el precio de un pedido límite representa el precio más bajo con el que debe coincidir cualquier fragmento, el precio en un pedido de ejecución inmediata representa el límite más bajo del Precio promedio ponderado de volumen (”VWAP”) para todo el volumen coincidente. Así, por ejemplo, un pedido de ejecución inmediata con el precio = 5,4 y un tamaño = 10 podría coincidir con £2 a 5,5, £6 a 5,4 y £2 a 5,3.

Ejemplos

Pedido de ejecución inmediata que caducó:





El pedido de ejecución inmediata solicita un tamaño mínimo de 3,00:





Parámetro de versión del mercado

Hemos agregado un parámetro opcional adicional ‘marketVersion’ a las operaciones ‘’placeOrders y‘’replaceOrders. Los datos de MarketBook, que contienen los datos dinámicos en un mercado, incluidos sus precios, siempre han devuelto una ‘versión’ de mercado entero. Esta ‘versión’ se incrementa cuando ocurren eventos importantes, eliminación de corredor, cambio en juego, etc. Ahora, al pasar esa versión como ‘marketVersion’ con sus pedidos, puede especificar que si la versión del mercado se ha incrementado más allá de ese valor, sus pedidos deben caducar y no presentarse para la coincidencia.

Esta funcionalidad debe ser útil para aquellos que quieran apostar justo a la ‘salida’ real de una carrera de caballos o en el inicio de un evento deportivo, pero deben estar seguros de que no están apostando inadvertidamente en los primeros segundos del juego después del inicio. Asimismo, en los mercados de fútbol administrado, puede evitar que sus apuestas alcancen el Exchange después de que se haya modificado el mercado tras la anotación de un gol, etc.

Notas sobre el comportamiento de ‘versión'

El valor ‘versión del mercado’ (en listMarketBook y ESA) se incrementa para cualquiera y todos los cambios en el mercado.

Sin embargo, para evitar el bloqueo falso de apuestas hacemos un seguimiento del último cambio de material (que definimos como uno realizado bajo suspensión**), y solo aceptamos apuestas con esa versión o una versión posterior.


** Esto incluye lo siguiente:

Adición y eliminación de corredor

Cambio en juego

Caducidad o anulación de apuestas (por ejemplo, los goles marcados en el mercado futbolístico administrado)

Pero no (por ejemplo) la actualización de tiempos de cancha en tenis o tiempo de salida en golf, ya que se conocen con más exactitud en el día.


Apuesta al pago o ganancia/riesgo

Haga una apuesta y especifique su objetivo en cuanto a pago, ganancias o riesgo, en lugar de la apuesta del apostador a favor (’tamaño').

Actualmente, la mejor ejecución, que garantiza que recibirá el mejor precio posible, significa que recibe un mayor pago potencial para la misma apuesta (o un riesgo de pago potencial menor para la misma apuesta del apostador a favor, por capas).

Si desea beneficiarse y recibir el mismo pago potencial que solicitó originalmente, pero con una apuesta menor, ahora puede especificar un LimitOrder (placeOrders), un ‘betTargetType’ opcional de ‘PAGO’ o ‘BACKERS_PROFIT’ (lo último es idéntico al riesgo en capas) y un ‘betTargetSize” que representa el valor de ese pago o ganancia, junto con el parámetro 'Precio' habitual para representar su precio límite. Su apuesta se hará coincidir para lograr ese pago o ganancia en el precio especificado o mejor.

Si todo o una parte del pedido no coincide después de alcanzar el Exchange, la parte que no coincide se expresará en el precio estándar y los términos de la apuesta de quienes están a favor (al dividir el resto del pago que no coincide por el precio, o la ganancia que no coincide por el precio - 1, y se coloca en la cola de lo que no tiene coincidencia); después de este punto, la apuesta se comporta como cualquier otra.

Ejemplos

Hacer una apuesta a favor dirigida a una ganancia de £2





Hacer una apuesta en contra dirigida a un pago de £10







Capacidad para hacer apuestas mínimas a mayores precios

Con el fin de permitir a sus clientes hacer apuestas menores en selecciones de precio más largo, se ha agregado una propiedad adicional a nuestros Parámetros de moneda: “Pago de apuesta mín.".

Actualmente son válidas las apuestas donde lo apostado a favor tiene el ‘tamaño de apuesta mín.’ o está por encima de este para la moneda en cuestión (£2 para GBP) . Además, las apuestas por debajo de este valor son válidas si el pago de la apuesta es igual o mayor que el valor de ‘Pago de apuesta Mín.’: £10 para GBP. Por ejemplo, una apuesta de £1 a 10 o 10p a 100 o 1p a 1000 son todas válidas, ya que todas apuntan a un pago de £10 o más.

Tenga en cuenta lo siguiente: Esta función solo está activada para el Reino Unido y los clientes internacionales y no en las jurisdicciones .it, .es, .dk.

Apuesta Each Way

La apuesta Each Way está disponible a través de la API. Los mercados Each Way se pueden identificar como marketType EACH_WAY utilizando listMarketCatalogue. El divisor que se aplica al mercado EACH_WAY es devuelto por listMarketCatalogue a través de MARKET_DESCRIPTION MarketProjection.

Consulte la tabla que indica cómo el “divisor Each-Way” está determinado para tipos específicos de carreras:


(1) El número de corredores en el momento de creación del mercado; los términos del lugar son fijos para la duración del mercado (como el mercado de Betfair Place) que no depende del número de corredores a la salida (como los mercados Fixed Odds EW)

No vamos a ofrecer mercados EW si el número de corredores en el momento de creación del mercado es 4 o menos

Incrementos de precios de Betfair

A continuación, se muestra una lista de incrementos de precios por ‘grupo’ de precios. Hacer una apuesta fuera de estos incrementos dará como resultado un error INVALID_ODDS

Mercados de probabilidades



Mercados de goles totales y hándicap asiático


Parámetros de moneda

Guía para las monedas disponibles y los tamaños de apuestas mínimas.


cancelOrders

Operación

replaceOrders

Operación


updateOrders

Operación







Apuesta de precio inicial de Betfair (BSP)

El precio inicial de Betfair se determinará mediante el equilibrio de las apuestas de clientes que deseen apostar a favor y en contra en el precio inicial y obtener coincidencia en los mercados de Exchange de Betfair para equilibrar cualquier demanda residual.

El precio inicial de Betfair se calculará exactamente para garantizar las probabilidades más justas y transparentes posibles para los apostadores a favor y en contra. No es necesario que el BSP tenga en cuenta un margen de ganancia, sino que se calcula al comienzo de un evento mirando la relación entre las cantidades de dinero solicitadas a SP, al oponer las partes de las apuestas. Para dar un precio aún más exacto, vamos a utilizar el dinero en la medida de lo posible que se esté negociando en el intercambio al inicio del evento. Esto da un fiel reflejo de la opinión pública en una selección.

¿Cómo se calcula el BSP?

El precio cercano se basa en el dinero actualmente en el sitio en SP, así como el dinero sin coincidencia en la misma selección en el intercambio. Para comprender esto correctamente, es necesario entender primero el cálculo del precio lejano, que solo tiene en cuenta las apuestas del SP que se han hecho. El precio lejano no es tan complicado, pero no tan preciso y solo representa el dinero en el sitio en SP.

Excepto el dinero solicitado a un precio fijo en el intercambio, si hay £1000 en apuestas a favor en una selección en SP y £6000 
en riesgos en contra, podemos devolver un SP en el inicio del evento de 6/1 (7,0).

Sin embargo, si hubo apuestas a favor por un valor de £6000 en la selección y £1000 en riesgos en contra, devolveríamos un SP de 1/6 (1,17). Estos son cálculos del precio lejano.

El cálculo del precio inicial final se produce cuando se cambia el mercado en juego. Esto es cuando se reconcilia el mercado.

Se puede encontrar información adicional y demostración detallada de cómo se calcula el precio de SP de Betfair a través de https://promo.betfair.com/betfairsp
/FAQs_theBasics.html


Excepciones de apuestas


Excepciones






Enumeraciones de apuestas

Enumeraciones






























































Definiciones de tipo de apuestas

Definiciones de tipo









































































































### API de cuentas

Extremos


A continuación, busque los detalles de los extremos de la API de cuentas actual.

Exchange global


Operaciones de cuentas




Resumen



createDeveloperAppKeys

Operación




getAccountDetails

Operación





getAccountFunds

Operación



getDeveloperAppKeys

Operación


getAccountStatement

listCurrencyRates


transferFunds

Operación


Excepciones de cuentas

Excepciones


Enumeraciones de cuentas

Enumeraciones









TypeDefinitions de cuentas

Definiciones de tipo































### API de pulso

- Documentación detallada
- Operaciones
- Definiciones de tipo
- Excepciones
- Típica interacción

Esta operación de pulso se proporciona para permitir a los clientes cancelar automáticamente sus apuestas sin coincidencia en el caso de que los clientes de API pierdan conectividad con la API de Betfair.

Exchange del Reino Unido


Exchange italiano


Exchange español


Resumen de la operación


Documentación detallada

Heartbeat

Operaciones
Pulso
Eventos
Definiciones de tipo
HeartbeatReport
Enumeraciones
ActionPerformed
Excepciones
APINGException

Operaciones


Eventos
Esta interfaz no define ningún evento.

Definiciones de tipo



Enumeraciones


Excepciones


Típica interacción

CONFIGURACIÓN


[{"jsonrpc": “2.0", "method": “HeartbeatAPING/v1.0/heartbeat", "params": {"preferredTimeoutSeconds":"10"}, "id": 1}] 

[{"jsonrpc":"2.0","result":{"actualTimeoutSeconds":10,"actionPerformed":"NONE"},"id":1}]

REINICIO

[{"jsonrpc": “2.0", "method": “HeartbeatAPING/v1.0/heartbeat", "params": {"preferredTimeoutSeconds":"0"}, "id": 1}]

[{"jsonrpc":"2.0","result":{"actualTimeoutSeconds":0,"actionPerformed":"NONE"},"id":1}]

NUEVA CONFIGURACIÓN DE PULSO

[{"jsonrpc": “2.0", "method": “HeartbeatAPING/v1.0/heartbeat", "params": {"preferredTimeoutSeconds":"10"}, "id": 1}] 

[{"jsonrpc":"2.0","result":{"actualTimeoutSeconds":10,"actionPerformed":"NONE"},"id":1}]
Debe poder restablecer el pulso si pasa un valor de actualTimeoutSeconds”:0 y, luego, lo reinicia al establecer el valor requerido.


EJEMPLO DE RESPUESTA SI NO SE RECIBIÓ EL PULSO DENTRO DEL TIEMPO ESPECIFICADO

[{"jsonrpc": “2.0", "method": “HeartbeatAPING/v1.0/heartbeat", "params": {"preferredTimeoutSeconds":"10"}, "id": 1}] 

[{"jsonrpc":"2.0","result":{"actualTimeoutSeconds":10,"actionPerformed":"ALL_BETS_CANCELLED"},"id":1}]


### API de estado de carrera

La operación listRaceDetails se proporciona para permitir a los clientes determinar el estado de un mercado de carrera de caballos o galgos, tanto antes como después del inicio de la carrera. Esta información está disponible solo para las carreras del Reino Unido e Irlanda.

listRaceDetails
Resumen de la operación
Operaciones
Eventos
Definiciones de tipo
Alias de tipo
Enumeraciones
Excepciones

listRaceDetails


Resumen de la operación


Operaciones
listRaceDetails
Eventos
Definiciones de tipo
RaceDetails
Enum
RaceStatus
Responsecode
Excepciones
APINGException


Operaciones

Eventos
Esta interfaz no define ningún evento.

Definiciones de tipo


Alias de tipo





Enumeraciones


Excepciones

### Documentos de definición de interfaz

Los siguientes documentos proporcionan una descripción de la interfaz legible por máquina para API-NG en formato XML.

Actualizado el 4 de abril de 2017

SportsAPING.xml

AccountAPING.xml

HeartbeatAPING.xml

## Información adicional

### Incrementos de precios de Betfair

A continuación, se muestra una lista de incrementos de precios por ‘grupo’ de precios. Hacer una apuesta fuera de estos incrementos dará como resultado un error INVALID_ODDS

Mercados de probabilidades


BettingType ASIAN_HANDICAP_SINGLE_LINE & ASIAN_HANDICAP_DOUBLE_LINE only




### Parámetros de moneda

Guía para las monedas disponibles y los tamaños de apuestas mínimas.




### Abreviaturas del hipódromo

Las listas de abreviaturas del hipódromo para carreras de caballos y de galgos están disponibles a través de horsegrayhoundcourseabbreviations.xls
### Descripción de metadatos del corredor

La RUNNER_METADATA que devuelve listMarketCatalogue para las Carreras de caballos (cuando está disponible) se describe en la siguiente tabla.



Términos de uso: Consulte http://form.timeform.betfair.com/termsofuse con respecto a los datos anteriores.


### Zonas horarias y formato de hora

Todas las horas están en GMT y según el formato de ISO 8601 (http://en.wikipedia.org/wiki/ISO_8601). Se pueden convertir a su zona horaria local utilizando el campo de zona horaria devuelto por la operación getAccountDetails o en la zona horaria del mercado local utilizando la zona horaria devuelta para el evento por listMarketCatalogue

Para sincronizar con la hora del servidor de Betfair, le recomendamos que utilice el grupo de servidores NTP que se muestra a través de http://www.pool.ntp.org/zone/europe


En la siguiente tabla, se enumeran las zonas horarias devueltas por la API junto con su significado.






### Los códigos de error más comunes




### Apuestas virtuales

El Exchange de Betfair utiliza un algoritmo de ‘incidencia cruzada’ para mostrar los mejores precios posibles (apuestas) disponibles al tener en cuenta las ofertas a favor y en contra (apuestas sin coincidencias) en todas las selecciones.





Una de las formas más fáciles para comprender cómo se generan las apuestas virtuales para la coincidencia cruzada es analizando un par de ejemplos.

Considere el siguiente mercado y qué pasaría si hacemos una gran apuesta a favor del empate a 1,01:



Sin una coincidencia cruzada, esta apuesta coincidiría en tres partes:
1) £150 a 5,0,
2) £250 a 3,0,
y £999 a 1,01 con todo lo demás que quede sin coincidencia.

Con la coincidencia cruzada podemos hacer algo mejor.

Tenemos una apuesta a favor de Newcastle por £120 a 2,0 y una apuesta a favor de Chelsea por £150 a 3,0 
(se muestra en rosa la parte disponible para apostar en contra del mercado).





Estas dos apuestas pueden coincidir con una apuesta a favor del empate a un precio de 6,0 ya que 2,0, 3,0 y 6,0 forman una reserva del 100 %. Para asegurarnos de que la reserva sea equilibrada, elegimos que las apuestas sean inversamente proporcionales a los precios.

Esto significa que tomamos los £120 a 2,0 en Newcastle, solo £80 a 3,0 en Chelsea y £40 a 6,0 en el empate, que es la primera apuesta virtual.

Ahora tenemos una apuesta a favor de Newcastle por £75 a 2,5 y una apuesta a favor de Chelsea por £70 a 3,0 (de nuevo se muestra en rosa la parte disponible para apostar en contra del mercado).

Estas dos apuestas pueden coincidir con una apuesta a favor del empate a un precio de 3,75 ya que 2,5, 3,0 y 3,75 también forman una reserva del 100 %.

Equilibrar las apuestas significa que tomamos los £75 a 2,5 en Newcastle, solo £62.5 a 3,0 en Chelsea y £50 a 3,75 en el empate, que es la segunda apuesta virtual. Debido a que 3,75 es menor que 5,0, el valor de £150 a 5,0 sería la primera coincidencia seguida por £50 a 3,75. Si continuáramos con este proceso, obtendríamos mayor coincidencias a 1,50 y 1,05, pero para poder mostrar la visión del mercado, tenemos los mejores 3 precios para las apuestas a favor disponibles en el empate, y así podemos dejar de calcular las apuestas virtuales. Las apuestas virtuales son las apuestas que habrían coincidido si hubiéramos recibido una apuesta lo suficientemente grande a favor a 1,01; en este ejemplo, £40 a 6,0 y £50 a 3,75. Tomamos estas apuestas virtuales y las combinamos con las apuestas existentes en el mercado para generar la siguiente visión de mercado (con las apuestas virtuales en verde).





Se repite el proceso para obtener las apuestas virtuales en contra (apuestas a favor disponibles) de Newcastle y Chelsea.


Aquí tenemos un mercado ligeramente diferente (como antes, elegido para que los números sean fáciles), considere qué pasaría si hiciéramos una gran apuesta en contra a 1000 en el empate.




Sin la coincidencia cruzada, esta apuesta coincidiría con tres partes: 1) £100 a 10,0, 2) £50 a 50,0 y £2 a 1000 con todo lo demás que quede sin coincidencia. Con la coincidencia cruzada podemos hacer algo mejor. Tenemos una apuesta en contra de Newcastle por £300 a 2,0 y una apuesta en contra de Chelsea por £150 a 3,0 (se muestra en azul la parte disponible para apostar a favor del mercado). Estas dos apuestas pueden coincidir con una apuesta en contra del empate a un precio de 6,0 ya que 2,0, 3,0 y 6,0 forman una reserva del 100 %. Para asegurarnos de que la reserva sea equilibrada, elegimos que las apuestas sean inversamente proporcionales a los precios. Esto significa que tomamos solo £225 a 2,0 en Newcastle, £150 a 3,0 en Chelsea y £75 a 6,0 en el empate, que es la primera apuesta virtual.

Si suponemos que estas apuestas dieron coincidencias, el mercado sería así:



Tenemos una apuesta en contra de Newcastle por £75 a 2,0 y una apuesta en contra de Chelsea por £250 a 2,4 (se muestra en azul la parte disponible para apostar a favor del mercado). Estas dos apuestas pueden coincidir con una apuesta en contra del empate a un precio de 12,0 ya que 2,0, 2,4 y 12,0 también forman una reserva del 100 %.
Equilibrar las apuestas significa que tomamos los £75 a 2,0 en Newcastle, solo £62.5 a 2,4 en Chelsea y £12,50 a 12,0 en el empate, que es la segunda apuesta virtual.

Esto genera el siguiente mercado:




Esta vez no podemos continuar el proceso porque no hay un precio válido para una apuesta virtual al empate que resulte en una reserva del 100 %, por lo que podemos detener el cálculo de las apuestas virtuales. Nuevamente, las apuestas virtuales son las apuestas que habrían coincidido si hubiéramos recibido una apuesta lo suficientemente grande en contra a 1000; en este ejemplo, £75 a 6,0 y £12.50 a 12,0. Tomamos estas apuestas virtuales y las combinamos con las apuestas existentes en el mercado para generar la siguiente visión de mercado (con las apuestas virtuales en naranja).



### Especificación de la configuración regional

La especificación de la configuración regional determina el idioma devuelto para nombres de deportes y mercados. Es un parámetro opcional que puede especificar si desea recuperar nombres en un idioma diferente del idioma especificado para la cuenta. Por ejemplo, si el idioma de la cuenta está especificado como inglés, puede usar el parámetro regional para recuperar nombres de mercados o deportes que no estén en inglés.

El código de idioma está basado en la norma ISO 639-1 que define los códigos de dos letras, como "en" y "fr".

Los siguientes idiomas están disponibles, pero tenga en cuenta que no todos los mercados están traducidos en todos los idiomas:



| Interfaz | Extremo | Prefijo de JSON-RPC | Ejemplo de <methodname> |
| --- | --- | --- | --- |
| JSON-RPC | https://api.betfair.com/exchange/betting/json-rpc/v1 | <methodname> | SportsAPING/v1.0/listMarketBook |
| JSON REST | https://api.betfair.com/exchange/betting/rest/v1.0/ |  | listMarketBook/ |
| Interfaz | Extremo | Prefijo de JSON-RPC | Ejemplo de <methodname> |
| --- | --- | --- | --- |
| JSON-RPC | https://api.betfair.com/exchange/account/json-rpc/v1 | <methodname> | AccountAPING/v1.0/getAccountFunds |
| JSON REST | https://api.betfair.com/exchange/account/rest/v1.0 |  | getAccountFunds/ |
|  |
| --- |
| {
"filter" : { }
} |
|  |
|  |
| --- |
| import requests import json

endpoint = "https://api.betfair.com/exchange/betting/rest/v1.0/"

header = { 'X-Application' : 'APP_KEY_HERE', 'X-Authentication' : 'SESSION_TOKEN_HERE' ,'content-type' : 'application/json' }

json_req='{"filter":{ }}'

url = endpoint + "listEventTypes/"

response = requests.post(url, data=json_req, headers=header)


print json.dumps(json.loads(response.text), indent=3) |
|  |
|  |
| --- |
| {
"params": {
"filter": 
{ "eventTypeIds": [1]
}
},
"jsonrpc": "2.0",
"method": "SportsAPING/v1.0/listCompetitions", 
"id": 1
} |
|  |
|  |
| --- |
| import requests 
import json

url="https://api.betfair.com/exchange/betting/json-rpc/v1"
header = { 'X-Application' : 'APP_KEY_HERE', 'X-Authentication' : 'SESSION_TOKEN' ,'content-type' : 'application/json' }

jsonrpc_req='{"jsonrpc": "2.0", "method": "SportsAPING/v1.0/listEventTypes", "params": {"filter":{ }}, "id": 1}'

response = requests.post(url, data=jsonrpc_req, headers=header) 

print json.dumps(json.loads(response.text), indent=3) |
|  |
| {
"jsonrpc": "2.0", 
"result": [
{
"eventType": { 
"id": "468328",
"name": "Handball"
},
"marketCount": 59
},
{
"eventType": { 
"id": "1",
"name": "Soccer"
},
"marketCount": 14792
},
{
"eventType": { 
"id": "2",
"name": "Tennis"
},
"marketCount": 51
},
{
"eventType": { 
"id": "3",
"name": "Golf"
,
"marketCount": 12
},
{
"eventType": { 
"id": "4",
"name": "Cricket"
},
"marketCount": 139
},
{
"eventType": { 
"id": "5",
"name": "Rugby Union"
},
"marketCount": 100
},
{
"eventType": { 
"id": "6",
"name": "Boxing"
},
"marketCount": 12
},
{
"eventType": { 
"id": "7",
"name": "Horse Racing"
},
"marketCount": 187
},
{
"eventType": { 
"id": "8",
"name": "Motor Sport"
},
"marketCount": 3
},
{
"eventType": { 
"id": "7524",
"name": "Ice Hockey"
},
"marketCount": 8
},
{
"eventType": { 
"id": "10",
"name": "Special Bets"
},
"marketCount": 30
},
{
"eventType": { 
"id": "451485",
"name": "Winter Sports"
},
"marketCount": 7
},
{
"eventType": { 
"id": "7522",
"name": "Basketball"
},
"marketCount": 559
},

{
"eventType": { 
"id": "1477",
"name": "Rugby League"
},
"marketCount": 3
},
{
"eventType": { 
"id": "4339",
"name": "Greyhound Racing"
},
"marketCount": 269
},
{
"eventType": { 
"id": "2378961",
"name": "Politics"
},
"marketCount": 19
},
{
"eventType": { 
"id": "6231",
"name": "Financial Bets"
},
"marketCount": 51
},
{
"eventType": { 
"id": "998917",
"name": "Volleyball"
},
"marketCount": 69
},
{
"eventType": { 
"id": "998919",
"name": "Bandy"
},
"marketCount": 2
},
{
"eventType": { 
"id": "998918",
"name": "Bowls"
},
"marketCount": 10
},

{
"eventType": { 
"id": "3503",
"name": "Darts"
},
"marketCount": 446
},
{
"eventType": { 
"id": "72382",
"name": "Pool"
},
"marketCount": 1
},
{
"eventType": { 
"id": "6422",
"name": "Snooker"
},
"marketCount": 3
},
{
"eventType": { 
"id": "6423",
"name": "American Football"
},
"marketCount": 86
},
{
"eventType": { 
"id": "7511",
"name": "Baseball"
},
"marketCount": 1
}
],
"id": 1
} |
| --- |
|  |
| En esta sección, se muestra cómo se puede llamar a la API de Apuestas para recuperar información.

En esta sección, se incluyen ejemplos de cómo solicitar la siguiente información en formato jsonrpc: 

Solicitar una lista de los tipos de eventos disponibles
Solicitar una lista de eventos para un tipo de evento 
Solicitar información sobre el mercado para un evento 
Competiciones de fútbol
Precios del mercado que hace una apuesta 
Cómo hacer una apuesta SP
Recuperación de los detalles de una apuesta hecha en un mercado 
Recuperación del resultado de un mercado asentado |
| --- |
|  |
| --- |
| [
{
"jsonrpc": "2.0", 
"result": [
{
"eventType": { 
"id": "468328",
"name": "Handball"
},
"marketCount": 11
},
{
eventType": { 
"id": "1",
"name": "Soccer"
},
"marketCount": 25388
},
{
"eventType": { 
"id": "2",
"name": "Tennis"
},
"marketCount": 402
},
{
"eventType": { 
"id": "3",
"name": "Golf"
},
"marketCount": 79
},
{
"eventType": { 
"id": "4",
"name": "Cricket"
},
"marketCount": 192
},
{
"eventType": { 
"id": "5",
"name": "Rugby Union"
},
"marketCount": 233
},
{
"eventType": { 
"id": "6",
"name": "Boxing"
},
"marketCount": 18
},
{
"eventType": { 
"id": "7",
"name": "Horse Racing"
},
"marketCount": 398
},
{
"eventType": { 
"id": "8",
"name": "Motor Sport"
},
marketCount": 50
},
{
"eventType": { 
"id": "7524",
"name": "Ice Hockey"
},
"marketCount": 521
},
{
"eventType": { 
"id": "10",
"name": "Special Bets"
},
"marketCount": 39
},
{
"eventType": { 
"id": "451485",
"name": "Winter Sports"
},
"marketCount": 7
},
{
"eventType": { 
"id": "11",
"name": "Cycling"
},
"marketCount": 1
},
{
"eventType": { 
"id": "136332",
"name": "Chess"
},
"marketCount": 1
},
{
"eventType": { 
"id": "7522",
"name": "Basketball"
},
"marketCount": 617
},
{
"eventType": { 
"id": "1477",
"name": "Rugby League"
},
"marketCount": 91
},
{
"eventType": {
id": "4339",
"name": "Greyhound Racing"
},
"marketCount": 298
},
{
"eventType": { 
"id": "6231",
"name": "Financial Bets"
},
"marketCount": 44
},
{
"eventType": {
"id": "2378961",
"name": "Politics"
},
"marketCount": 23
},
{
"eventType": { 
"id": "998917",
"name": "Volleyball"
},
"marketCount": 66
},
{
"eventType": { 
"id": "998919",
"name": "Bandy"
},
"marketCount": 4
},
{
"eventType": { 
"id": "998918",
"name": "Bowls"
},
"marketCount": 17
},
{
"eventType": {
"id": "26420387",
"name": "Mixed Martial Arts"
},
"marketCount": 52
},
{
"eventType": { 
"id": "3503",
"name": "Darts"
},
"marketCount": 21
,
{
"eventType": {
"id": "2152880",
"name": "Gaelic Games"
},
"marketCount": 2
},
{
"eventType": { 
"id": "6422",
"name": "Snooker"
},
"marketCount": 22
},
{
"eventType": { 
"id": "6423",
"name": "American Football"
},
"marketCount": 171
},
{
"eventType": { 
"id": "315220",
"name": "Poker"
},
"marketCount": 2
},
{
"eventType": { 
"id": "7511",
"name": "Baseball"
},
"marketCount": 7
}
],
"id": 1
}
] |
|  |
|  |
| --- |
| [
{
"jsonrpc": "2.0",
"method": "SportsAPING/v1.0/listEvents", "params": {
"filter": {
"eventTypeIds": [ "1"
],
"marketStartTime": {
"from": "2014-03-13T00:00:00Z",
"to": "2014-03-13T23:59:00Z"
}
}
},
"id": 1
}
] |
|  |
|  |
| --- |
| [
{
"jsonrpc": "2.0", "result": [
{
"event": {
"id": "27165668",
"name": "Al-Wahda (KSA) v Hajer (KSA)", "countryCode": "SA",
"timezone": "GMT",
"openDate": "2014-03-13T13:30:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165665",
"name": "Al Hussein v Mansheyat Bani Hasan", "countryCode": "JO",
"timezone": "GMT",
"openDate": "2014-03-13T15:00:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165425",
"name": "Daily Goals", "countryCode": "GB", "timezone": "Europe/London",
"openDate": "2014-03-13T18:00:00.000Z"
},
"marketCount": 1
},
{
"event": {
"id": "27165667",
"name": "Al Jeel v Al Draih", "countryCode": "SA",
"timezone": "GMT",
"openDate": "2014-03-13T12:45:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165677",
"name": "Daventry Town v Kettering", "countryCode": "GB",
"timezone": "GMT",
"openDate": "2014-03-13T19:45:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27160160",
"name": "Porto v Napoli", "countryCode": "PT",
"timezone": "GMT",
"openDate": "2014-03-13T18:00:00.000Z"
},
"marketCount": 84
},
{
"event": {
"id": "27162435",
"name": "Bishops Stortford v Hayes And Yeading", "countryCode": "GB",
"timezone": "GMT",
"openDate": "2014-03-13T15:00:00.000Z"
},
"marketCount": 2
"event": {
"id": "27166333",
"name": "Bosnia U19 v Serbia U19", "timezone": "GMT",
"openDate": "2014-03-13T12:30:00.000Z"
},
"marketCount": 25
},
{
"event": {
"id": "27162436",
"name": "Maidenhead v Gosport Borough", "countryCode": "GB",
"timezone": "GMT",
"openDate": "2014-03-13T19:45:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165673",
"name": "ASA Tel Aviv Uni (W) v FC Ramat Hasharon (W)", "countryCode": "IL",
"timezone": "GMT",
"openDate": "2014-03-13T17:15:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27164435",
"name": "Forest Green v Braintree", "countryCode": "GB",
"timezone": "GMT",
"openDate": "2014-03-13T19:45:00.000Z"
},
"marketCount": 15
},
{
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165684",
"name": "FC Lokomotivi Tbilisi v FC Saburtalo Tbilisi", 
"countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165686",
"name": "FC Sasco Tbilisi v Matchak Khelvachauri", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
},
"marketCount": 18
},
{
"event": {
"id": "27165680",
"name": "FAR Rabat v Maghreb Fes", "countryCode": "MA",
"timezone": "GMT",
"openDate": "2014-03-13T15:30:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165683",
"name": "FC Kolkheti Khobi v Samgurali Tskaltubo", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165682",
"name": "FC Dila Gori II v FC Dinamo Batumi", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165693",
"name": "Tilbury FC v Redbridge", "countryCode": "GB",
"timezone": "GMT",
"openDate": "2014-03-13T19:45:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165688",
"name": "HUJK Emmaste v Kohtla-Jarve JK Jarve", "countryCode": "EE",
"timezone": "GMT",
"openDate": "2014-03-13T17:00:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165690",
"name": "M Kishronot Hadera (W) v Maccabi Holon FC
(W)",
"countryCode": "IL",
"timezone": "GMT",
"openDate": "2014-03-13T17:30:00.000Z"
,
"marketCount": 20
},
{
"event": {
"id": "27166225",
"name": "Litex Lovech v Cherno More", "countryCode": "BG",
"timezone": "GMT",
"openDate": "2014-03-13T15:30:00.000Z"
},
"marketCount": 27
},
{
"event": {
"id": "27162412",
"name": "KR Reykjavik v IA Akranes", "countryCode": "IS",
"timezone": "GMT",
"openDate": "2014-03-13T19:00:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27162473",
"name": "Atletico Huila v Tolima", 
"countryCode": "CO",
"timezone": "GMT",
"openDate": "2014-03-13T23:00:00.000Z"
},
"marketCount": 27
},
{
"event": {
"id": "27162413",
"name": "KV v Selfoss", "countryCode": "IS",
"timezone": "GMT",
"openDate": "2014-03-13T21:00:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165159",
"name": "August Town FC v Boys Town FC", "countryCode": "JM",
"timezone": "GMT",
"openDate": "2014-03-13T20:30:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27165161",
"name": "Bogota v CD Barranquilla", "countryCode": "CO",
"timezone": "GMT",
"openDate": "2014-03-13T20:00:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27166474",
"name": "Brasilia FC v Formosa", "countryCode": "BR",
"timezone": "GMT",
"openDate": "2014-03-13T19:00:00.000Z"
},
"marketCount": 15
},
{
"event": {
"id": "27162538",
"name": "Arsenal FC v Penarol", "countryCode": "AR",
"timezone": "GMT",
"openDate": "2014-03-13T22:00:00.000Z"
},
marketCount": 40
},
{
"event": {
"id": "27166478",
"name": "Ware FC v AFC Sudbury", "countryCode": "GB",
"timezone": "GMT",
"openDate": "2014-03-13T19:45:00.000Z"
},
"marketCount": 15
},
{
"event": {
"id": "27165505",
"name": "Tomsk v Tyumen", "countryCode": "RU",
"timezone": "GMT",
"openDate": "2014-03-13T11:30:00.000Z"
},
"marketCount": 28
},
{
"event": {
"id": "27166477",
"name": "Needham Market FC v Thurrock", "countryCode": "GB",
"timezone": "GMT",
"openDate": "2014-03-13T19:45:00.000Z"
},
"marketCount": 15
},
{
"event": {
"id": "27160154",
"name": "Lyon v Plzen", "countryCode": "FR",
"timezone": "GMT",
"openDate": "2014-03-13T20:05:00.000Z"
},
"marketCount": 41
},
{
"event": {
"id": "27160155",
"name": "Ludogorets v Valencia", "countryCode": "BG",
"timezone": "GMT",
"openDate": "2014-03-13T18:00:00.000Z"
},
"marketCount": 84
},
{
event": {
"id": "27160152",
"name": "Tottenham v Benfica", "countryCode": "GB",
"timezone": "GMT",
"openDate": "2014-03-13T20:05:00.000Z"
},
"marketCount": 84
},
{
"event": {
"id": "27162428",
"name": "Wadi Degla v El Shorta", "countryCode": "EG",
"timezone": "GMT",
"openDate": "2014-03-13T13:00:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27160158",
"name": "FC Basel v Red Bull Salzburg", "countryCode": "CH",
"timezone": "GMT",
"openDate": "2014-03-13T18:00:00.000Z"
},
"marketCount": 84
},
{
"event": {
"id": "27162427",
"name": "Ismaily v El Qanah", "countryCode": "EG",
"timezone": "GMT",
"openDate": "2014-03-13T13:00:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27160159",
"name": "AZ Alkmaar v Anzhi Makhachkala", "countryCode": "NL",
"timezone": "GMT",
"openDate": "2014-03-13T20:05:00.000Z"
},
"marketCount": 41
},
{
"event": {
"id": "27162426",
"name": "Al Ahly v El Entag El Harby",
"countryCode": "EG",
"timezone": "GMT",
"openDate": "2014-03-13T15:30:00.000Z"
},
"marketCount": 15
},
{
"event": {
"id": "27160156",
"name": "Sevilla v Betis", "countryCode": "ES",
"timezone": "GMT",
"openDate": "2014-03-13T20:05:00.000Z"
},
"marketCount": 84
},
{
"event": {
"id": "27160157",
"name": "Juventus v Fiorentina", "countryCode": "IT",
"timezone": "GMT",
"openDate": "2014-03-13T20:05:00.000Z"
},
"marketCount": 84
},
{
"event": {
"id": "27166336",
"name": "Becamex Binh Duong U19 v Khanh Hoa U19", "countryCode": "VN",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
},
"marketCount": 15
},
{
"event": {
"id": "27163800",
"name": "Lokomotiv Sofia v Chernomorets Burgas", "countryCode": "BG",
"timezone": "GMT",
"openDate": "2014-03-13T12:00:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27162481",
"name": "Ljungskile v Torslanda", "countryCode": "SE",
"timezone": "GMT",
"openDate": "2014-03-13T18:00:00.000Z"
},
"marketCount": 27
},
{
"event": {
"id": "27166338",
"name": "H Ironi Petah Tikva (W) v Maccabi Beer Sheva
(W)",
"countryCode": "IL",
"timezone": "GMT",
"openDate": "2014-03-13T18:15:00.000Z"
,
"marketCount": 15
},
{
"event": {
"id": "27163801",
"name": "Concord Rangers v Havant and W", "countryCode": "GB",
"timezone": "GMT",
"openDate": "2014-03-13T19:45:00.000Z"
},
"marketCount": 2
},
{
"event": {
"id": "27166340",
"name": "Maccabi Ironi Bat Yam v Hapoel Mahane Yehuda", "countryCode": "IL",
"timezone": "GMT",
"openDate": "2014-03-13T17:00:00.000Z"
},
"marketCount": 15
},
{
"event": {
"id": "27162418",
"name": "Courts Young Lions v Woodlands Wellington", "countryCode": "SG",
"timezone": "GMT",
"openDate": "2014-03-13T11:30:00.000Z"
},
"marketCount": 20
},
{
"event": {
"id": "27162417",
"name": "Balestier Khalsa v Tanjong Pagar Utd", "countryCode": "SG",
"timezone": "GMT",
"openDate": "2014-03-13T11:30:00.000Z"
},
"marketCount": 20
}
],
"id": 1
}
] |
|  |
|  |
| --- |
| [
{
"jsonrpc": "2.0",
"method": "SportsAPING/v1.0/listMarketCatalogue", "params": {
"filter": {
"eventIds": [
"27165685"
]
},
"maxResults": "200", "marketProjection": [
"COMPETITION", "EVENT", "EVENT_TYPE", "RUNNER_DESCRIPTION", "RUNNER_METADATA", "MARKET_START_TIME"
]
},
"id": 1
}
] |
|  |
|  |
| --- |
| [
{
"jsonrpc": "2.0", "result": [
{
"marketId": "1.113197547",
"marketName": "FC Betlemi Keda +1", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 12, "runners": [
{
"selectionId": 6843871, "runnerName": "FC Betlemi Keda +1",
"handicap": 0,,
"sortPriority": 1, "metadata": {
"runnerId": "63123618"
}
},
{
"selectionId": 6830600, "runnerName": "FC Samtredia -1", "handicap": 0,
"sortPriority": 2, "metadata": {
"runnerId": "63123619"
}
},
{
"selectionId": 151478, "runnerName": "Draw", "handicap": 0,
"sortPriority": 3, "metadata": {
"runnerId": "63123620"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197546",
"marketName": "FC Samtredia +1", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 0, "runners": [
{
"selectionId": 6830597, "runnerName": "FC Samtredia +1", "handicap": 0,
"sortPriority": 1, "metadata": {
runnerId": "63123615"
}
},
{
"selectionId": 6843874, "runnerName": "FC Betlemi Keda -1", "handicap": 0,
"sortPriority": 2, "metadata": {
"runnerId": "63123616"
}
},
{
"selectionId": 151478, "runnerName": "Draw", "handicap": 0,
"sortPriority": 3, "metadata": {
"runnerId": "63123617"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197492",
"marketName": "Total Goals", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 246.82, "runners": [
{
"selectionId": 285469, "runnerName": "1 goals or more", "handicap": -1,
"sortPriority": 1, "metadata": {
"runnerId": "63123486"
}
},

"selectionId": 285470, "runnerName": "2 goals or more", "handicap": -2,
"sortPriority": 2, "metadata": {
"runnerId": "63123487"
}
},
{
"selectionId": 285471, "runnerName": "3 goals or more", "handicap": -3,
"sortPriority": 3, "metadata": {
"runnerId": "63123488"
}
},
{
"selectionId": 2795170, "runnerName": "4 goals or more", "handicap": -4,
"sortPriority": 4, "metadata": {
"runnerId": "63123489"
}
},
{
"selectionId": 285473, "runnerName": "5 goals or more", "handicap": -5,
"sortPriority": 5, "metadata": {
"runnerId": "63123490"
}
},
{
"selectionId": 285474, "runnerName": "6 goals or more", "handicap": -6,
"sortPriority": 6, "metadata": {
"runnerId": "63123491"
}
},
{
"selectionId": 8215951, "runnerName": "7 goals or more", "handicap": -7,
"sortPriority": 7, "metadata": {
"runnerId": "63123492"
}

],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197491",
"marketName": "Match Odds",
"marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 7707.52, "runners": [
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 0,
"sortPriority": 1, "metadata": {
"runnerId": "63123483"
}
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 0,
"sortPriority": 2, "metadata": {
"runnerId": "63123484"
}
},
{
"selectionId": 58805, "runnerName": "The Draw", "handicap": 0,
"sortPriority": 3, "metadata": {
"runnerId": "63123485"
}
}
],
"eventType": {
id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197550",
"marketName": "Both teams to Score?", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 14.78, "runners": [
{
"selectionId": 30246, "runnerName": "Yes", "handicap": 0,
"sortPriority": 1, "metadata": {
"runnerId": "63123625"
}
},
{
"selectionId": 30247, "runnerName": "No", "handicap": 0,
"sortPriority": 2, "metadata": {
"runnerId": "63123626"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197501",
"marketName": "Next Goal",
"marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 3.34, "runners": [
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 0,
"sortPriority": 1, "metadata": {
"runnerId": "63123495"
}
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 0,
"sortPriority": 2, "metadata": {
"runnerId": "63123496"
}
},
{
"selectionId": 69852, "runnerName": "No Goal", "handicap": 0,
"sortPriority": 3, "metadata": {
"runnerId": "63123497"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},

"marketId": "1.113197502",
"marketName": "Over/Under 6.5 Goals", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 1255.79, "runners": [
{
"selectionId": 2542448, "runnerName": "Under 6.5 Goals", "handicap": 0,
"sortPriority": 1, "metadata": {
"runnerId": "63123498"
}
},
{
"selectionId": 2542449, "runnerName": "Over 6.5 Goals", "handicap": 0,
"sortPriority": 2, "metadata": {
"runnerId": "63123499"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197505",
"marketName": "Correct Score", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 2380.92, "runners": [
{
"selectionId": 1,
"runnerName": "0 - 0",
"handicap": 0,
"sortPriority": 1, "metadata": {
"runnerId": "63123505"
}
},
{
"selectionId": 4,
"runnerName": "0 - 1",
"handicap": 0,
"sortPriority": 2, "metadata": {
"runnerId": "63123506"
}
},
{
"selectionId": 9,
"runnerName": "0 - 2",
"handicap": 0,
"sortPriority": 3, "metadata": {
"runnerId": "63123507"
}
},
{
"selectionId": 16,
"runnerName": "0 - 3",
"handicap": 0,
"sortPriority": 4, "metadata": {
"runnerId": "63123508"
}
},
{
"selectionId": 2,
"runnerName": "1 - 0",
"handicap": 0,
"sortPriority": 5, "metadata": {
"runnerId": "63123509"
}
},
{
"selectionId": 3,
"runnerName": "1 - 1",
"handicap": 0,
"sortPriority": 6, "metadata": {
"runnerId": "63123510"
}
},
{
"selectionId": 8,
"runnerName": "1 - 2",
"handicap": 0,
"sortPriority": 7,
"metadata": {
"runnerId": "63123511"
}
},
{
"selectionId": 15,
"runnerName": "1 - 3",
"handicap": 0,
"sortPriority": 8, "metadata": {
"runnerId": "63123512"
}
},
{
"selectionId": 5,
"runnerName": "2 - 0",
"handicap": 0,
"sortPriority": 9, "metadata": {
"runnerId": "63123513"
}
},
{
"selectionId": 6,
"runnerName": "2 - 1",
"handicap": 0,
"sortPriority": 10, "metadata": {
"runnerId": "63123514"
}
},
{
"selectionId": 7,
"runnerName": "2 - 2",
"handicap": 0,
"sortPriority": 11, "metadata": {
"runnerId": "63123515"
}
},
{
"selectionId": 14,
"runnerName": "2 - 3",
"handicap": 0,
"sortPriority": 12, "metadata": {
"runnerId": "63123516"
}
},
{
"selectionId": 10,
"runnerName": "3 - 0",
"handicap": 0,
"sortPriority": 13, "metadata": {
"runnerId": "63123517"
}
},
{
"selectionId": 11,
"runnerName": "3 - 1",
"handicap": 0,
"sortPriority": 14, "metadata": {
"runnerId": "63123518"
}
},
{
"selectionId": 12,
"runnerName": "3 - 2",
"handicap": 0,
"sortPriority": 15, "metadata": {
"runnerId": "63123519"
}
},
{
"selectionId": 13,
"runnerName": "3 - 3",
"handicap": 0,
"sortPriority": 16, "metadata": {
"runnerId": "63123520"
}
},
{
"selectionId": 4506345, "runnerName": "Any Unquoted ", "handicap": 0,
"sortPriority": 17, "metadata": {
"runnerId": "63123521"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda",
"countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197506",
"marketName": "Over/Under 2.5 Goals", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 4149.36, "runners": [
{
"selectionId": 47972, "runnerName": "Under 2.5 Goals", "handicap": 0,
"sortPriority": 1, "metadata": {
"runnerId": "63123522"
}
},
{
"selectionId": 47973, "runnerName": "Over 2.5 Goals", "handicap": 0,
"sortPriority": 2, "metadata": {
"runnerId": "63123523"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197504",
"marketName": "Over/Under 5.5 Goals", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 2216.24, "runners": [
{
selectionId": 1485567, "runnerName": "Under 5.5 Goals", "handicap": 0,
"sortPriority": 1, "metadata": {
"runnerId": "63123503"
}
},
{
"selectionId": 1485568, "runnerName": "Over 5.5 Goals", "handicap": 0,
"sortPriority": 2, "metadata": {
"runnerId": "63123504"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197509",
"marketName": "Half Time/Full Time", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 97.3, "runners": [
{
"selectionId": 6830596,
"runnerName": "FC Samtredia/FC Samtredia", "handicap": 0,
"sortPriority": 1, "metadata": {
"runnerId": "63123536"
}
},
{
"selectionId": 6830599, "runnerName": "FC Samtredia/Draw", "handicap": 0
"sortPriority": 2, "metadata": {
"runnerId": "63123537"
}
},
{
"selectionId": 8380726,
"runnerName": "FC Samtredia/FC Betlemi Ked", "handicap": 0,
"sortPriority": 3, "metadata": {
"runnerId": "63123538"
}
},
{
"selectionId": 6830595, "runnerName": "Draw/FC Samtredia", "handicap": 0,
"sortPriority": 4, "metadata": {
"runnerId": "63123539"
}
},
{
"selectionId": 3710152, "runnerName": "Draw/Draw", "handicap": 0,
"sortPriority": 5, "metadata": {
"runnerId": "63123540"
}
},
{
"selectionId": 6843869, "runnerName": "Draw/FC Betlemi Ked", "handicap": 0,
"sortPriority": 6, "metadata": {
"runnerId": "63123541"
}
},
{
"selectionId": 8380727,
"runnerName": "FC Betlemi Ked/FC Samtredia", "handicap": 0,
"sortPriority": 7, "metadata": {
"runnerId": "63123542"
}
},
{
"selectionId": 6843873, "runnerName": "FC Betlemi Ked/Draw",
"handicap": 0,
"sortPriority": 8, "metadata": {
"runnerId": "63123543"
}
},
{
"selectionId": 6843870,
"runnerName": "FC Betlemi Ked/FC Betlemi Ked", "handicap": 0,
"sortPriority": 9, "metadata": {
"runnerId": "63123544"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197510",
"marketName": "Over/Under 1.5 Goals", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 1879.69, "runners": [
{
"selectionId": 1221385, "runnerName": "Under 1.5 Goals", "handicap": 0,
"sortPriority": 1, "metadata": {
"runnerId": "63123545"
}
},
{
"selectionId": 1221386, "runnerName": "Over 1.5 Goals", "handicap": 0,
"sortPriority": 2, "metadata": {
"runnerId": "63123546"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197507",
"marketName": "Over/Under 4.5 Goals", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 3189.28, "runners": [
{
"selectionId": 1222347, "runnerName": "Under 4.5 Goals", "handicap": 0,
"sortPriority": 1, "metadata": {
"runnerId": "63123524"
}
},
{
"selectionId": 1222346, "runnerName": "Over 4.5 Goals", "handicap": 0,
"sortPriority": 2, "metadata": {
"runnerId": "63123525"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197511",
"marketName": "Over/Under 3.5 Goals", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 3934.41, "runners": [
{
"selectionId": 1222344, "runnerName": "Under 3.5 Goals", "handicap": 0,
"sortPriority": 1, "metadata": {
"runnerId": "63123547"
}
},
{
"selectionId": 1222345, "runnerName": "Over 3.5 Goals", "handicap": 0,
"sortPriority": 2, "metadata": {
"runnerId": "63123548"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
},
{
"marketId": "1.113197512",
"marketName": "Asian Handicap", "marketStartTime": "2014-03-13T11:00:00.000Z",
"totalMatched": 1599.38, 
"runners": [
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -4,
"sortPriority": 1
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 4,
"sortPriority": 2
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -3.75,
"sortPriority": 3
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 3.75,
"sortPriority": 4
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -3.5,
"sortPriority": 5
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 3.5,
"sortPriority": 6
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -3.25,
"sortPriority": 7
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 3.25,
"sortPriority": 8
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia",
"handicap": -3,
"sortPriority": 9
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 3,
"sortPriority": 10
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -2.75,
"sortPriority": 11
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 2.75,
"sortPriority": 12
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -2.5,
"sortPriority": 13
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 2.5,
"sortPriority": 14
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -2.25,
"sortPriority": 15
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 2.25,
"sortPriority": 16
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -2,
"sortPriority": 17
},
{
"selectionId": 6843866,
"runnerName": "FC Betlemi Keda", "handicap": 2,
"sortPriority": 18
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -1.75,
"sortPriority": 19
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 1.75,
"sortPriority": 20
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -1.5,
"sortPriority": 21
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 1.5,
"sortPriority": 22
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -1.25,
"sortPriority": 23
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 1.25,
"sortPriority": 24
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -1,
"sortPriority": 25
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 1,
"sortPriority": 26
},
{
selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -0.75,
"sortPriority": 27
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 0.75,
"sortPriority": 28
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -0.5,
"sortPriority": 29
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 0.5,
"sortPriority": 30
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": -0.25,
"sortPriority": 31
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 0.25,
"sortPriority": 32
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 0,
"sortPriority": 33
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": 0,
"sortPriority": 34
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 0.25,
"sortPriority": 35
},

"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -0.25,
"sortPriority": 36
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 0.5,
"sortPriority": 37
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -0.5,
"sortPriority": 38
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 0.75,
"sortPriority": 39
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -0.75,
"sortPriority": 40
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 1,
"sortPriority": 41
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -1,
"sortPriority": 42
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 1.25,
"sortPriority": 43
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -1.25,
"sortPriority": 44

{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 1.5,
"sortPriority": 45
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -1.5,
"sortPriority": 46
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 1.75,
"sortPriority": 47
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -1.75,
"sortPriority": 48
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 2,
"sortPriority": 49
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -2,
"sortPriority": 50
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 2.25,
"sortPriority": 51
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -2.25,
"sortPriority": 52
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 2.5,
"sortPriority": 53
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -2.5,
"sortPriority": 54
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 2.75,
"sortPriority": 55
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -2.75,
"sortPriority": 56
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 3,
"sortPriority": 57
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -3,
"sortPriority": 58
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 3.25,
"sortPriority": 59
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -3.25,
"sortPriority": 60
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 3.5,
"sortPriority": 61
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda",
"handicap": -3.5,
"sortPriority": 62
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 3.75,
"sortPriority": 63
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -3.75,
"sortPriority": 64
},
{
"selectionId": 6830593, "runnerName": "FC Samtredia", "handicap": 4,
"sortPriority": 65, "metadata": {
"runnerId": "63123613"
}
},
{
"selectionId": 6843866, "runnerName": "FC Betlemi Keda", "handicap": -4,
"sortPriority": 66, "metadata": {
"runnerId": "63123614"
}
}
],
"eventType": { "id": "1",
"name": "Soccer"
},
"competition": { "id": "2356065",
"name": "Pirveli Liga"
},
"event": {
"id": "27165685",
"name": "FC Samtredia v FC Betlemi Keda", "countryCode": "GE",
"timezone": "GMT",
"openDate": "2014-03-13T11:00:00.000Z"
}
}
],
"id": 1
}
] |
|  |
|  |
| --- |
| [
{
"jsonrpc": "2.0",
"method": "SportsAPING/v1.0/listMarketCatalogue", "params": {
"filter": {
"eventTypeIds": [ "7"
],
"marketTypeCodes": [ "WIN",
"PLACE"
],
"marketStartTime": {
"from": "2013-10-16T00:00:00Z",
"to": "2013-10-16T23:59:00Z"
}
},
"maxResults": "200", "marketProjection": [
"MARKET_START_TIME", "RUNNER_METADATA", "RUNNER_DESCRIPTION", "EVENT_TYPE", "EVENT", "COMPETITION"
]
},
"id": 1
}
] |
|  |
|  |
| --- |
| {
"jsonrpc": "2.0", "result": [
{
"marketCount": 16, "competition": {
"id": "833222",
"name": "Turkish Division 2"
}
},
{
"marketCount": 127, "competition": {
"id": "5",
"name": "A-League 2012/13"
}
},
{
"marketCount": 212, "competition": {
"id": "7",
"name": "Austrian Bundesliga"
}
},
{
"marketCount": 243, "competition": {
"id": "11",
"name": "Dutch Jupiler League"
}
},
{
"marketCount": 206,
"competition": { "id": "26207",
"name": "Greek Cup"
}
},
{
"marketCount": 117, "competition": {
"id": "2129602",
"name": "Professional Development League"
}
},
{
"marketCount": 68, "competition": {
"id": "803237",
"name": "Argentinian Primera B"
}
},
{
"marketCount": 1, "competition": {
"id": "1842928",
"name": "OTB Bank Liga"
}
}
],
"id": 1
} |
|  |
|  |
| --- |
| import requests 
import json

url="https://api.betfair.com/betting/json-rpc"
header = { 'X-Application' : "APP_KEY_HERE",	'X-Authentication : 'SESSION_TOKEN', 'content-type' : 'application/json' }


jsonrpc_req='{"jsonrpc": "2.0", "method": "SportsAPING/v1.0/listCompetitions", "params": {"filter":{ "eventTypeIds" : [1]	}}, "id": 1}'


print json.dumps(json.loads(jsonrpc_req), indent=3) 
print " "



response = requests.post(url, data=jsonrpc_req, headers=header) 

print json.dumps(json.loads(response.text), indent=3) |
|  |
|  |
| --- |
| [{
"jsonrpc": "2.0",
"method": "SportsAPING/v1.0/listMarketBook", "params": {
"marketIds": ["1.127771425"],
"priceProjection": {
"priceData": ["EX_BEST_OFFERS", "EX_TRADED"],
"virtualise": "true"
}
,
"id": 1
}][{
"jsonrpc": "2.0",
"result": [{
"marketId": "1.127771425",
"isMarketDataDelayed": false, "status": "OPEN",
"betDelay": 0, "bspReconciled": false, "complete": true, "inplay": false, "numberOfWinners": 1,
"numberOfRunners": 3,
"numberOfActiveRunners": 3,
"lastMatchTime": "2016-10-28T12:25:30.235Z",
"totalMatched": 188959.22,
"totalAvailable": 172932.96, "crossMatching": true, "runnersVoidable": false, "version": 1469071410, "runners": [{
"selectionId": 44790,
"handicap": 0.0,
"status": "ACTIVE", "lastPriceTraded": 7.0,
"totalMatched": 12835.46, "ex": {
"availableToBack": [{ "price": 7.0,
"size": 75.53
}, {
"price": 6.8,
"size": 538.6
}, {
"price": 6.6,
"size": 612.2
}],
"availableToLay": [{ "price": 7.2,
"size": 152.12
}, {
"price": 7.4,
"size": 1446.28
}, {
"price": 7.6,
"size": 1250.26
}],
"tradedVolume": [{ "price": 6.4,
"size": 3.0
}, {
"price": 6.6,
}, {
"price": 6.8,
"size": 1.42
}, {
"price": 7.0,
"size": 1736.55
}, {
"price": 7.2,
"size": 1601.31
}, {
"price": 7.4,
"size": 3580.1
}, {
"price": 7.6,
"size": 4236.59
}, {
"price": 7.8,
"size": 1367.18
}, {
"price": 8.0,
"size": 305.29
}, {
"price": 8.2,
"size": 0.39
}]
}
}, 
{
"selectionId": 489720,
"handicap": 0.0,
"status": "ACTIVE", "lastPriceTraded": 1.63,
"totalMatched": 163020.94, "ex": {
"availableToBack": [{ "price": 1.62,
"size": 4921.06
}, {
"price": 1.61,
"size": 3230.34
}, {
"price": 1.6,
"size": 2237.71
}],
"availableToLay": [{ "price": 1.63,
"size": 1001.76
}, {
"price": 1.64,
"size": 6737.59
}, {
"price": 1.65,
"size": 1701.27
],
"tradedVolume": [{ "price": 1.53,
"size": 31.38
}, {
"price": 1.54,
"size": 3.77
}, {
"price": 1.57,
"size": 3582.76
}, {
"price": 1.58,
"size": 12037.21
}, {
"price": 1.59,
"size": 16530.57
}, {
"price": 1.6,
"size": 54607.84
}, {
"price": 1.61,
"size": 36015.53
}, {
"price": 1.62,
"size": 21108.23
}, {
"price": 1.63,
"size": 17575.94
}, {
"price": 1.64,
"size": 1527.67
}]
}
}, {
"selectionId": 58805,
"handicap": 0.0,
"status": "ACTIVE", "lastPriceTraded": 4.2,
"totalMatched": 13102.81, "ex": {
"availableToBack": [{ "price": 4.1,
"size": 3243.85
}, {
"price": 4.0,
"size": 1158.17
}, {
"price": 3.95,
"size": 254.04
}],
"availableToLay": [{ "price": 4.2,
"size": 1701.15
, {
"price": 4.3,
"size": 3072.55
}, {
"price": 4.4,
"size": 2365.76
}],
"tradedVolume": [{ "price": 4.0,
"size": 457.79
}, {
"price": 4.1,
"size": 4434.67
}, {
"price": 4.2,
"size": 7845.01
}, {
"price": 4.3,
"size": 354.7
}, {
"price": 4.4,
"size": 6.6
}, {
"price": 4.9,
"size": 4.0
}]
}
}]
}],
"id": 1
}] |
|  |
|  |
| --- |
| [
{
"jsonrpc": "2.0",
"method": "SportsAPING/v1.0/placeOrders", "params": {
"marketId": "1.109850906",
"instructions": [
{
"selectionId": "237486",
"handicap": "0",
"side": "LAY", "orderType": "LIMIT", "limitOrder": {
"size": "2",
"price": "3", "persistenceType": "LAPSE"
}
}
]
},
"id": 1
}
] |
|  |
|  |
|  |
| --- |
| [
{
"jsonrpc": "2.0", "result": {
"marketId": "1.109850906",
"instructionReports": [
{
"instruction": { "selectionId": 237486,
"handicap": 0, "limitOrder": {
"size": 2,
"price": 3, "persistenceType": "LAPSE"
},
"orderType": "LIMIT", "side": "LAY"
},
"betId": "31242604945",
"placedDate": "2013-10-30T14:22:47.000Z",
"averagePriceMatched": 0,
"sizeMatched": 0, "status": "SUCCESS"
}
],
"status": "SUCCESS"
},
"id": 1
}
] |
|  |
|  |
| --- |
| [
{
"jsonrpc": "2.0",
"method": "SportsAPING/v1.0/placeOrders", "params": {
"marketId": "1.111836557",
"instructions": [
{
"selectionId": "5404312",
"handicap": "0",
"side": "BACK",
"orderType": "MARKET_ON_CLOSE", "marketOnCloseOrder": {
"liability": "2"
}
}
]
},
"id": 1
}
] |
|  |
|  |
| --- |
| [
{
"jsonrpc": "2.0", "result": {
"marketId": "1.111836557",
"instructionReports": [
{
"instruction": { "selectionId": 5404312,
"handicap": 0, "marketOnCloseOrder": {
"liability": 2
},
"orderType": "MARKET_ON_CLOSE", "side": "BACK"
},
"betId": "31645233727",
"placedDate": "2013-11-12T12:07:29.000Z",
"status": "SUCCESS"
}
],
"status": "SUCCESS"
},
"id": 1
}
] |
|  |
|  |
| --- |
| [{"jsonrpc": "2.0", "method": "SportsAPING/v1.0/listCurrentOrders", "params":
{"marketIds":["1.117020524"],"orderProjection":"ALL","dateRange":{}}, "id": 1}]
[{"jsonrpc":"2.0","result":{"currentOrders":[{"betId":"45496907354","marke tId":"1.117020524","selectionId":9170340,"handicap":0.0,"priceSize":{"pric e":10.0,"size":5.0},"bspLiability":0.0,"side":"BACK","status":"EXECUTABLE"
,"persistenceType":"LAPSE","orderType":"LIMIT","placedDate":"2015-01-22T13
:01:53.000Z","averagePriceMatched":0.0,"sizeMatched":0.0,"sizeRemaining":5
.0,"sizeLapsed":0.0,"sizeCancelled":0.0,"sizeVoided":0.0,"regulatorCode":" GIBRALTAR REGULATOR"}],"moreAvailable":false},"id":1}] |
|  |
|  |
| --- |
| [{"jsonrpc": "2.0", "method": "SportsAPING/v1.0/listMarketBook", "params":
{"marketIds":["1.114363660"],"priceProjection":{"priceData":["EX_BEST_OFFE RS"]}}, "id": 1}] |
|  |
|  |
| --- |
| [
{
"jsonrpc": "2.0", "result": [
{
"marketId": "1.114363660",
"isMarketDataDelayed": false, "status": "CLOSED", "betDelay": 0, "bspReconciled": false, "complete": true,
"inplay": false, "numberOfWinners": 1,
"numberOfRunners": 14,
"numberOfActiveRunners": 0,
"totalMatched": 0,
"totalAvailable": 0, "crossMatching": false, "runnersVoidable": false, "version": 767398001, "runners": [
{
"selectionId": 8611526,
"handicap": 0,
"status": "REMOVED", "adjustmentFactor": 9.1,
"removalDate": "2014-06-13T08:44:17.000Z",
"ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
},
{
"selectionId": 8611527,
"handicap": 0, "status": "REMOVED",
"adjustmentFactor": 3.5,
"removalDate": "2014-06-13T08:44:29.000Z",
"ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
},
{
"selectionId": 7920154,
"handicap": 0, "status": "WINNER",
"adjustmentFactor": 17.5, "ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
},
{
"selectionId": 1231425,
"handicap": 0, "status": "LOSER",
"adjustmentFactor": 4.3, "ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
},
{
"selectionId": 7533866,
"handicap": 0, "status": "LOSER",
"adjustmentFactor": 11.4, "ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
,
{
"selectionId": 8220841,
"handicap": 0, "status": "LOSER",
"adjustmentFactor": 5.4, "ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
},
{
"selectionId": 7533883,
"handicap": 0, "status": "LOSER",
"adjustmentFactor": 8.7, "ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
},
{
"selectionId": 8476712,
"handicap": 0, "status": "LOSER",
"adjustmentFactor": 8.7, "ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
},
{
"selectionId": 7012263,
"handicap": 0, "status": "LOSER",
"adjustmentFactor": 5.4, "ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
},
{
"selectionId": 7374225,
"handicap": 0, "status": "LOSER",
"adjustmentFactor": 8.7, "ex": {
"availableToBack": [], "availableToLay": [],
tradedVolume": []
}
},
{
"selectionId": 8611525,
"handicap": 0, "status": "LOSER",
"adjustmentFactor": 0.7, "ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
},
{
"selectionId": 7659121,
"handicap": 0, "status": "LOSER",
"adjustmentFactor": 26.8, "ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
},
{
"selectionId": 6996332,
"handicap": 0, "status": "LOSER",
"adjustmentFactor": 0.7, "ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
},
{
"selectionId": 7137541,
"handicap": 0, "status": "LOSER",
"adjustmentFactor": 1.7, "ex": {
"availableToBack": [], "availableToLay": [], "tradedVolume": []
}
}
]
}
],
"id": 1
}
] |
|  |
|  | Clave de aplicación retardada | Clave de aplicación en directo |
| --- | --- | --- |
| Se usa para | Desarrollo | Aplicaciones de apuestas 
en directo |
| Tarifa de activación | Ninguna | £299 |
| Datos de precios en directo | Retardada* | Sí |
| Realización de apuesta 
(Exchange [Intercambio] en directo) | Sí | Sí |
| API de secuencia | Sí (póngase en contacto con Soporte para desarrolladores) | Sí (en la aplicación) |
| Niveles de precios | 3 | Todos |
| Coincidencia total por selección | No disponible | Sí |
| Coincidencia total por mercado | Sí | No |
| *La demora varía entre 1 y 60 segundos |  |  |
| Nombre | Descripción | Muestra |
| --- | --- | --- |
| Accept (obligatorio). | Encabezado que indica que la respuesta se debe devolver como JSON. | application/json |
| X-Authentication (obligatorio) | Encabezado que representa el token de sesión que debe mantenerse activo | Token de sesión |
| X-Application (opcional) | Encabezado de la clave de la aplicación que usó el cliente para identificar el producto. | Clave de aplicación |
| Nombre | Descripción | Muestra |
| --- | --- | --- |
| Accept (obligatorio). | Encabezado que indica que la respuesta se debe devolver como JSON. | application/json |
| X-Authentication (obligatorio) | Encabezado que representa el token de sesión creado al iniciar sesión. | Token de sesión |
| X-Application (opcional) | Encabezado de la clave de la aplicación que usó el cliente para identificar el producto. | Clave de aplicación |
| Nombre de archivo | Descripción |
| --- | --- |
| client-2048.key | La clave privada. Este archivo es necesario para poder utilizar el certificado, debe estar protegido y no debe compartirse con nadie. |
| client-2048.csr | Una solicitud de firma de certificado. Este archivo ya no es necesario y puede eliminarse. |
| client-2048.crt | El certificado. Este archivo no es sensible en términos de seguridad y se puede compartir. |
|  |
| --- |
| cat client-2048.crt client-2048.key > client-2048.pem |
|  |
|  |
| --- |
| https://identitysso.betfair.com/api/certlogin |
|  |
| loginStatus | Descripción |
| --- | --- |
| INVALID_USERNAME_OR_PASSWORD | el nombre de usuario o la contraseña no son válidos |
| ACCOUNT_NOW_LOCKED | la cuenta ha sido bloqueada |
| ACCOUNT_ALREADY_LOCKED | la cuenta está bloqueada |
| PENDING_AUTH | autenticación pendiente |
| TELBET_TERMS_CONDITIONS_NA | términos y condiciones de Telbet rechazados |
| DUPLICATE_CARDS | tarjetas duplicadas |
| SECURITY_QUESTION_WRONG_3X | el usuario ha escrito mal la respuesta de seguridad 3 veces |
| KYC_SUSPEND | KYC suspendido |
| SUSPENDED | la cuenta está suspendida |
| CLOSED | la cuenta está cerrada |
| SELF_EXCLUDED | la cuenta se ha autoexcluido |
| INVALID_CONNECTIVITY_TO_REGULATOR_DK | no se puede acceder al regulador de DK debido a algunos problemas internos en el sistema detrás o en el regulador; se incluyen casos de tiempo de espera. |
| NOT_AUTHORIZED_BY_REGULATOR_DK | el usuario identificado con las credenciales proporcionadas no está autorizado en las jurisdicciones de DK debido a políticas de los reguladores. Ej.: el usuario para quien se creó esta sesión no tiene permiso para actuar (jugar, apostar) en la jurisdicción de DK. |
| INVALID_CONNECTIVITY_TO_REGULATOR_IT | no se puede acceder al regulador de IT debido a algunos problemas internos en el sistema detrás o en el regulador; se incluyen casos de tiempo de espera. |
| NOT_AUTHORIZED_BY_REGULATOR_IT | el usuario identificado con las credenciales proporcionadas no está autorizado en las jurisdicciones de IT debido a políticas de los reguladores. Ej.: el usuario para quien se creó esta sesión no tiene permiso para actuar (jugar, apostar) en la jurisdicción de IT. |
| SECURITY_RESTRICTED_LOCATION | la cuenta está restringida debido a preocupaciones de seguridad |
| BETTING_RESTRICTED_LOCATION | a la cuenta se accede desde una ubicación donde las apuestas están restringidas |
| TRADING_MASTER | Cuenta maestra de transacciones |
| TRADING_MASTER_SUSPENDED | Cuenta maestra de transacciones suspendida |
| AGENT_CLIENT_MASTER | Agente maestro del cliente |
| AGENT_CLIENT_MASTER_SUSPENDED | Agente maestro del cliente suspendido |
| DANISH_AUTHORIZATION_REQUIRED | Se requiere autorización de Dinamarca |
| SPAIN_MIGRATION_REQUIRED | Se requiere migración de España |
| DENMARK_MIGRATION_REQUIRED | Se requiere migración de Dinamarca |
| SPANISH_TERMS_ACCEPTANCE_REQUIRED | Se debe aceptar la última versión de los términos y condiciones de España. Debe iniciar sesión en el sitio web para aceptar las nuevas condiciones. |
| ITALIAN_CONTRACT_ACCEPTANCE_REQUIRED | Se debe aceptar la última versión del contrato italiano. Debe iniciar sesión en el sitio web para aceptar las nuevas condiciones. |
| CERT_AUTH_REQUIRED | Se necesita un certificado o no se pudo autenticar con el certificado presente |
| CHANGE_PASSWORD_REQUIRED | Se requiere cambio de contraseña |
| PERSONAL_MESSAGE_REQUIRED | Se requiere mensaje personal para el usuario |
| INTERNATIONAL_TERMS_ACCEPTANCE_REQUIRED | Se deben aceptar los términos y condiciones internacionales más recientes antes de iniciar la sesión. |
| EMAIL_LOGIN_NOT_ALLOWED | Esta cuenta no ha optado por iniciar sesión con la dirección de correo electrónico |
| MULTIPLE_USERS_WITH_SAME_CREDENTIAL | Hay más de una cuenta con la misma credencial |
| ACCOUNT_PENDING_PASSWORD_CHANGE | La cuenta debe someterse a la recuperación de contraseña para reactivarse a través Https://identitysso.b etfair.com/view/recoverpassword |
| TEMPORARY_BAN_TOO_MANY_REQUESTS | El límite para las solicitudes de inicio de sesión exitoso por minuto se ha superado. Se prohibirán los nuevos intentos de inicio de sesión durante 20 minutos |
| ITALIAN_PROFILING_ACCEPTANCE_REQUIRED | Debe iniciar sesión en el sitio web para aceptar las nuevas condiciones |
|  |
| --- |
| package com.test.aping.client;



import org.apache.http.HttpEntity; import org.apache.http.HttpResponse; import org.apache.http.NameValuePair;
import org.apache.http.client.entity.UrlEncodedFormEntity; import org.apache.http.client.methods.HttpPost;
import org.apache.http.conn.ClientConnectionManager; import org.apache.http.conn.scheme.Scheme;
import org.apache.http.conn.ssl.SSLSocketFactory; import org.apache.http.conn.ssl.StrictHostnameVerifier; import org.apache.http.impl.client.DefaultHttpClient; import org.apache.http.message.BasicNameValuePair; import org.apache.http.util.EntityUtils;

import javax.net.ssl.KeyManager;
import javax.net.ssl.KeyManagerFactory; import javax.net.ssl.SSLContext;
import java.io.File;
import java.io.FileInputStream; import java.io.InputStream; import java.security.KeyStore;
import java.security.SecureRandom; import java.util.ArrayList;
import java.util.List;


public class HttpClientSSO { private static int port = 443;
public static void main(String[] args) throws Exception { DefaultHttpClient httpClient = new DefaultHttpClient();
try {
SSLContext ctx = SSLContext.getInstance("TLS"); KeyManager[] keyManagers = getKeyManagers("pkcs12", new
FileInputStream(new File("C:\\sslcerts\\client-2048.p12")), "password"); ctx.init(keyManagers, null, new SecureRandom()); SSLSocketFactory factory = new SSLSocketFactory(ctx, new
StrictHostnameVerifier());

ClientConnectionManager manager = httpClient.getConnectionManager();
manager.getSchemeRegistry().register(new Scheme("https", port, factory));
HttpPost httpPost = new
HttpPost("https://identitysso.betfair.com/api/certlogin");
List<NameValuePair> nvps = new ArrayList<NameValuePair>(); nvps.add(new BasicNameValuePair("username", "testuser")); nvps.add(new BasicNameValuePair("password", "testpassword"));

httpPost.setEntity(new UrlEncodedFormEntity(nvps));



httpPost.setHeader("X-Application","appkey");


System.out.println("executing request" + httpPost.getRequestLine());

HttpResponse response = httpClient.execute(httpPost); HttpEntity entity = response.getEntity();

System.out.println("---------------------------------------");
System.out.println(response.getStatusLine()); if (entity != null) {
String responseString = EntityUtils.toString(entity);
//extract the session token from responsestring System.out.println("responseString" + responseString);
}

} finally {
httpClient.getConnectionManager().shutdown();
}
}



private static KeyManager[] getKeyManagers(String keyStoreType, InputStream keyStoreFile, String keyStorePassword) throws Exception {
KeyStore keyStore = KeyStore.getInstance(keyStoreType); keyStore.load(keyStoreFile, keyStorePassword.toCharArray()); KeyManagerFactory kmf =
KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm()); kmf.init(keyStore, keyStorePassword.toCharArray());
return kmf.getKeyManagers();
}
} |
|  |
| errorCode |  |
| --- | --- |
| ACCOUNT_ALREADY_LOCKED | la cuenta está bloqueada |
| ACCOUNT_NOW_LOCKED | la cuenta ya está bloqueada |
| ACCOUNT_PENDING_PASSWORD_CHANGE | la cuenta debe someterse a la recuperación de la contraseña para reactivar a través de https://identitysso.betfair. com/view/recoverpassword |
| AGENT_CLIENT_MASTER | Agente maestro del cliente |
| AGENT_CLIENT_MASTER_SUSPENDED | Agente maestro del cliente suspendido |
| BETTING_RESTRICTED_LOCATION | a la cuenta se accede desde una ubicación donde las apuestas están restringidas |
| CERT_AUTH_REQUIRED | Se necesita un certificado o no se pudo autenticar con el certificado presente |
| CHANGE_PASSWORD_REQUIRED | se requiere cambio de contraseña |
| CLOSED | la cuenta está cerrada |
| DANISH_AUTHORIZATION_REQUIRED | se requiere autorización de Dinamarca |
| DENMARK_MIGRATION_REQUIRED | se requiere migración de Dinamarca |
| DUPLICATE_CARDS | tarjetas duplicadas |
| EMAIL_LOGIN_NOT_ALLOWED | Esta cuenta no ha optado por iniciar sesión con la dirección de correo electrónico |
| INVALID_CONNECTIVITY_TO_REGULATOR_DK | no se puede acceder al regulador de DK debido a algunos problemas internos en el sistema detrás o en el regulador; se incluyen casos de tiempo de espera. |
| INVALID_CONNECTIVITY_TO_REGULATOR_IT | no se puede acceder al regulador de IT debido a algunos problemas internos en el sistema detrás o en el regulador; se incluyen casos de tiempo de espera. |
| INVALID_USERNAME_OR_PASSWORD | el nombre de usuario o la contraseña no son válidos |
| ITALIAN_CONTRACT_ACCEPTANCE_REQUIRED | Se debe aceptar la última versión del contrato italiano. |
| KYC_SUSPEND | KYC suspendido |
| NOT_AUTHORIZED_BY_REGULATOR_DK | el usuario identificado con las credenciales proporcionadas no está autorizado en las jurisdicciones de DK debido a políticas de los reguladores. Ej.: el usuario para quien se creó esta sesión no tiene permiso para actuar (jugar, apostar) en la jurisdicción de DK. |
| NOT_AUTHORIZED_BY_REGULATOR_IT | el usuario identificado con las credenciales proporcionadas no está autorizado en las jurisdicciones de IT debido a políticas de los reguladores. Ej.: el usuario para quien se creó esta sesión no tiene permiso para actuar (jugar, apostar) en la jurisdicción de IT. |
| MULTIPLE_USERS_WITH_SAME_CREDENTIAL | Hay más de una cuenta con la misma credencial |
| PENDING_AUTH | autenticación pendiente |
| PERSONAL_MESSAGE_REQUIRED | se requiere mensaje personal para el usuario |
| SECURITY_QUESTION_WRONG_3X | el usuario ha escrito mal la respuesta de la pregunta de seguridad 3 veces |
| SECURITY_RESTRICTED_LOCATION | la cuenta está restringida debido a preocupaciones de seguridad |
| SELF_EXCLUDED | la cuenta se ha autoexcluido |
| SPAIN_MIGRATION_REQUIRED | se requiere migración de España |
| SPANISH_TERMS_ACCEPTANCE_REQUIRED | Se debe aceptar la última versión de los términos y condiciones de España. |
| SUSPENDED | la cuenta está suspendida |
| TELBET_TERMS_CONDITIONS_NA | términos y condiciones de Telbet rechazados |
| TRADING_MASTER | Cuenta maestra de transacciones |
| TRADING_MASTER_SUSPENDED | Cuenta maestra de transacciones suspendida |
| TEMPORARY_BAN_TOO_MANY_REQUESTS | El límite para las solicitudes de inicio de sesión exitoso por minuto se ha superado. Se prohibirán los nuevos intentos de inicio de sesión durante 20 minutos |
| --- | --- |
| Nombre | Descripción | Muestra |
| --- | --- | --- |
| producto (obligatorio) | El producto para el que se utiliza la página de inicio de sesión y en el que el usuario va a hacer el inicio de sesión. Esto debe ser la clave de la aplicación. | “IhDSui3ODdsdwo" |
| url (obligatorio) | La dirección URL a la que el navegador debe redirigirse en caso de un inicio de sesión con éxito. De forma predeterminada, solo se admitirá https://www.betfair.com | https://www.betfair.com |
|  |
| --- |
| https://identitysso.betfair.com/api/login |
|  |
| Nombre | Descripción | Muestra |
| --- | --- | --- |
| username (obligatorio) | El nombre de usuario que se debe utilizar para el inicio de sesión |  |
| password (obligatorio) | La contraseña que se debe utilizar para el inicio de sesión. Para los clientes con autenticación fuerte, esta debe ser su contraseña con un código de autenticación de 
2 factores anexado a la cadena de la contraseña. |  |
| Nombre | Descripción | Muestra |
| --- | --- | --- |
| Accept (obligatorio). | Señales que indican que la respuesta se debe devolver como JSON. | application/json |
| X-Application (obligatorio) | AppKey utilizada por el cliente para identificar el producto. |  |
| loginStatus | Descripción |
| --- | --- |
| TRADING_MASTER_SUSPENDED | Cuenta maestra de transacciones suspendida |
| TRADING_MASTER | Cuenta maestra de transacciones |
| TELBET_TERMS_CONDITIONS_NA | términos y condiciones de Telbet rechazados |
| SUSPENDED | la cuenta está suspendida |
| SPANISH_TERMS_ACCEPTANCE_REQUIRED | Se debe aceptar la última versión de los términos y condiciones de España. |
| SPAIN_MIGRATION_REQUIRED | Se requiere migración de España |
| SELF_EXCLUDED | la cuenta se ha autoexcluido |
| SECURITY_RESTRICTED_LOCATION | la cuenta está restringida debido a preocupaciones de seguridad |
| SECURITY_QUESTION_WRONG_3X | el usuario ha escrito mal la respuesta de la pregunta de seguridad 3 veces |
| PERSONAL_MESSAGE_REQUIRED | se requiere mensaje personal para el usuario |
| PENDING_AUTH | autenticación pendiente |
| NOT_AUTHORIZED_BY_REGULATOR_IT | el usuario identificado con las credenciales proporcionadas no está autorizado en las jurisdicciones de IT debido a políticas de los reguladores. Ej.: el usuario para quien se creó esta sesión no tiene permiso para actuar (jugar, apostar) en la jurisdicción de IT. |
| NOT_AUTHORIZED_BY_REGULATOR_DK | el usuario identificado con las credenciales proporcionadas no está autorizado en las jurisdicciones de DK debido a políticas de los reguladores. Ej.: el usuario para quien se creó esta sesión no tiene permiso para actuar (jugar, apostar) en la jurisdicción de DK. |
| KYC_SUSPEND | KYC suspendido |
| ITALIAN_CONTRACT_ACCEPTANCE_REQUIRED | Se debe aceptar la última versión del contrato italiano. |
| INVALID_USERNAME_OR_PASSWORD | el nombre de usuario o la contraseña no son válidos |
| INVALID_CONNECTIVITY_TO_REGULATOR_IT | no se puede acceder al regulador de IT debido a algunos problemas internos en el sistema detrás o en el regulador; se incluyen casos de tiempo de espera. |
| INVALID_CONNECTIVITY_TO_REGULATOR_DK | no se puede acceder al regulador de DK debido a algunos problemas internos en el sistema detrás o en el regulador; se incluyen casos de tiempo de espera. |
| DUPLICATE_CARDS | tarjetas duplicadas |
| DENMARK_MIGRATION_REQUIRED | Se requiere migración de Dinamarca |
| DANISH_AUTHORIZATION_REQUIRED | Se requiere autorización de Dinamarca |
| CLOSED | la cuenta está cerrada |
| CHANGE_PASSWORD_REQUIRED | se requiere cambio de contraseña |
| CERT_AUTH_REQUIRED | Se necesita un certificado o no se pudo autenticar con el certificado presente |
| BETTING_RESTRICTED_LOCATION | a la cuenta se accede desde una ubicación donde las apuestas están restringidas |
| AGENT_CLIENT_MASTER_SUSPENDED | Agente maestro del cliente suspendido |
| AGENT_CLIENT_MASTER | Agente maestro del cliente |
| ACCOUNT_NOW_LOCKED | la cuenta estaba bloqueada |
| ACCOUNT_ALREADY_LOCKED | la cuenta ya está bloqueada |
| TEMPORARY_BAN_TOO_MANY_REQUESTS | El límite para las solicitudes de inicio de sesión exitoso por minuto se ha superado. Se prohibirán los nuevos intentos de inicio de sesión durante 20 minutos |
| ACCOUNT_PENDING_PASSWORD_CHANGE | la cuenta debe someterse a la recuperación de la contraseña para reactivar a través https://identitysso.betfair. com/view/recoverpassword |
| ITALIAN_PROFILING_ACCEPTANCE_REQUIRED | Debe iniciar sesión en el sitio web para aceptar las nuevas condiciones |
| MarketProjection | Peso |
| --- | --- |
| MARKET_DESCRIPTION | 1 |
| RUNNER_DESCRIPTION | 0 |
| EVENT | 0 |
| EVENT_TYPE | 0 |
| COMPETITION | 0 |
| RUNNER_METADATA | 1 |
| MARKET_START_TIME | 0 |
| PriceProjection | Peso |
| --- | --- |
| Nulo (sin PriceProjection establecido) | 2 |
| SP_AVAILABLE | 3 |
| SP_TRADED | 7 |
| EX_BEST_OFFERS | 5 |
| EX_ALL_OFFERS | 17 |
| EX_TRADED | 17 |
| PriceProjection | Peso |
| --- | --- |
| EX_BEST_OFFERS + EX_TRADED | 20 |
| EX_ALL_OFFERS + EX_TRADED | 32 |
| PriceProjection | Peso |
| --- | --- |
| No aplica | 4 |
| Versión | Descripción | Fecha |
| --- | --- | --- |
| V 2.3 | Actualización para incluir la API de estado de carrera con las operaciones de listRaceDetails | 26-10-2015 |
| V 2.2 | Actualizado para incluir el campo eachWayDivisor en la respuesta listMarketCatalogue | 21-04-2015 |
| V 2.1 | Actualizado para incluir el campo de país adicional en la respuesta de getAccountDetails | 09-01-2015 |
| V 2.0 | Actualizado para incluir transferFunds, la operación de updateApplicationSubscription y actualizaciones para getAccountfunds | 29-09-2014 |
| V 1.9 | Actualizado para incluir los datos de navegación para las aplicaciones | 26-08-2014 |
| V.1.8 | Actualizado para incluir cambios en el manejo de errores en listCurrentOrders | 14-07-2014 |
| V.1.7 | Actualizado para incluir cambios en getAccountFunds y la API de servicios de proveedor | 16-06-2014 |
| V.1.6 | Actualizado para incluir getAccountStatement y listCurrencyRates | 29-04-2014 |
| V.1.5 | Actualizado para incluir la API de pulso | 09-04-2014 |
| V.1.4 | Actualizado para incluir cambios en listClearedOrders y listMarketCatalogue | 24-02-2014 |
| V.1.3 | Introducción de la funcionalidad de listMarketProfitAndLoss en la API de apuestas | 03-02-2014 |
| V.1.2 | Introducción de la funcionalidad de listClearedOrders en la API de apuestas | 17-12-2013 |
| V.1.1 | Actualizaciones en la API de proveedores, listCurrentOrders y adición de extremo para el Exchange (Intercambio) australiano | 07-10-2013 |
| V1.0 | Introducción de la funcionalidad de los servicios de proveedor e inicio de sesión, traslado hacia los extremos finales | 29-07-2013 |
| V0.4 | Introducción de la funcionalidad de cuenta adicional (getAccountFunds y getAccountDetails) | 01-07-2013 |
| V0.3 | Introducción de API-NG de cuenta | 03-06-2013 |
| V0.2 | Introducción de la funcionalidad de apuestas y listCurrentOrders | 20-05-2013 |
| V0.1 | Versión inicial | 09-12-2012 |
| Exchange | Método HTTP | Extremo |
| --- | --- | --- |
| REINO UNIDO | GET | https://api.betfair.com/exchange/betting/rest/v1/en/navigation/menu.json |
| ITALIA | GET | https://api.betfair.it/exchange/betting/rest/v1/en/navigation/menu.json |
| ESPAÑA | GET | https://api.betfair.es/exchange/betting/rest/v1/en/navigation/menu.json |
| Interfaz | Extremo | Prefijo de JSON-RPC | Ejemplo de <methodname> |
| --- | --- | --- | --- |
| JSON-RPC | https://api.betfair.com/exchange/betting/json-rpc/v1 | <methodname> | SportsAPING/v1.0/listMarketBook |
| JSON REST | https://api.betfair.com/exchange/betting/rest/v1.0/ |  | listMarketBook/ |
| Tipo | Operación | Descripción |
| --- | --- | --- |
| Lista< EventTypeResult > | listEventTypes (filtro MarketFilter, Stringlocale ) | Devuelve una lista de tipos de eventos (p. ej.: Deportes) asociados con los mercados seleccionados por el MarketFilter. |
| Lista< CompetitionResult > | listCompetitions (filtro MarketFilter, Stringlocale) | Devuelve una lista de competencias (p. ej.: Mundial de Fútbol 2013) asociada con los mercados seleccionados por el MarketFilter. Actualmente, solo los mercados de fútbol tienen una competencia asociada. |
| Lista< TimeRangeResult > | listTimeRanges (filtro MarketFilter, granularidad TimeGranularity) | Devuelve una lista de rangos de tiempo en la granularidad especificada en la solicitud (p. ej.: de 3 p.m. a 4 p.m., del 14 de agosto al 15 de agosto) asociada con los mercados seleccionados por el MarketFilter. |
| Lista< EventResult > | listEvents (filtro MarketFilter, Stringlocale) | Devuelve una lista de eventos (p. ej.: Reading vs. Man United) asociados con los mercados seleccionados por el MarketFilter. |
| Lista< MarketTypeResult > | listMarketTypes (filtro MarketFilter, Stringlocale) | Devuelve una lista de los tipos de mercado (p. ej.: MATCH_ODDS, NEXT_GOAL)
asociados con los mercados seleccionados por el MarketFilter. Los tipos de mercado son siempre los mismos, independientemente de la configuración regional. |
| --- | --- | --- |
| Lista< CountryCodeResult > | listCountries (filtro MarketFilter, Stringlocale) | Devuelve una lista de países asociados con los mercados seleccionados por el MarketFilter. |
| Lista< VenueResult > | listVenues (filtro MarketFilter, Stringlocale) | Devuelve una lista de lugares (p. ej.: Cheltenham, Ascot) asociados con los mercados seleccionados por el MarketFilter. Actualmente, solo los mercados de carreras de caballos se asocian con una sede. |
| Lista< MarketCatalogue > | listMarketCatalogue (filtro MarketFilter, Set< MarketProjection >m arketProjection, MarketSort sort, int maxResults, Stringlocale) | Devuelve una lista de la información acerca de los mercados publicados (ACTIVO/SUSPENDIDO) que no cambia (o cambia muy raramente). |
| Lista< MarketBook > | listMarketBook (List<String>marketIds, PriceProjection priceProj ection, OrderProjection orderProjection, MatchProjection matchProjec tion, StringcurrencyCode, Stringlocale, Date matchedSince, Set<BetId> betIds) | Devuelve una lista de los datos dinámicos de los mercados. Los datos dinámicos incluyen los precios, la situación del mercado, el estado de selecciones, el volumen negociado y el estado de los pedidos que haya realizado en el mercado |
| Lista<MarketBook> | Lista<MarketBook> listRunnerBook (MarketId marketId, Selection Id selectionId, double handicap, PriceProjection priceProjection, Ord erProjection orderProjection, MatchProjection matchProjection, boolean includeOverallPosition, boolean partitionMatchedByStrategyRef, Set<String> customerStrategyRefs, StringcurrencyCode, Stringlocale, Date matchedSince, Set<BetId> betIds) muestra APINGException | Devuelve una lista de los datos dinámicos sobre un mercado y un corredor especificado.
Los datos dinámicos incluyen los precios, la situación del mercado, el estado de selecciones, el volumen negociado y el estado de los pedidos que haya realizado en el mercado. |
| Lista<MarketProfitAndLoss> | listMarketProfitAndLoss (Set<MarketId> marketIds, boolean includeSettledBets, boolean includeBspBets, boolean netOfCommission) | Recupera pérdidas y ganancias para una lista determinada de mercados abiertos. Los valores se calculan usando apuestas que coincidan y opcionalmente apuestas realizadas |
| CurrentOrderSummaryReport | listCurrentOrders (Set<String>betIds, Set<String>marketIds, Order Projection orderProjection, TimeRange placedDateRange, OrderBy o derBy, SortDir sortDir, intfromRecord, intrecordCount) | Devuelve una lista de sus pedidos actuales. |
| ClearedOrderSummaryReport | listClearedOrders (BetStatus betStatus, Set<EventTypeId> eventTypeIds, Set<EventId> eventIds, Set<MarketId> marketIds, Set<RunnerId> runnerIds, Set<BetId> betIds, Side side, TimeRange settledDateRange, GroupBy groupBy, boolean includeItemDescription, String locale, int fromRecord, int recordCount) | Devuelve una lista de las apuestas realizadas según el estado de la apuesta, ordenadas por fecha |
| PlaceExecutionReport | placeOrders (StringmarketId, Lista<PlaceInstruction> instrucciones, StringcustomerRef, MarketVersion marketVersion, String customerStrategyRef, boolean async) | Colocar nuevas órdenes en el mercado. |
| CancelExecutionReport | cancelOrders (StringmarketId, Lista<CancelInstruction>instructio ns, StringcustomerRef) | Cancelar todas las apuestas O cancelar todas las apuestas en un mercado O cancelar total o parcialmente pedidos particulares en un mercado |
| --- | --- | --- |
| ReplaceExecutionReport | replaceOrders (StringmarketId, Lista< ReplaceInstruction> instrucciones, StringcustomerRef, MarketVersion marketVersion, boolean async) | Esta operación es lógicamente una cancelación por volumen seguida de una colocación por volumen. En primer lugar, se realiza la cancelación y, luego, se hacen los nuevos pedidos. |
| UpdateExecutionReport | updateOrders (StringmarketId, Lista< UpdateInstruction> instrucciones, StringcustomerRef) | Actualizar los campos que cambien sin exposición |
| listCompetitions | listCompetitions | listCompetitions | listCompetitions | listCompetitions | listCompetitions | listCompetitions |
| --- | --- | --- | --- | --- | --- | --- |
|  | Lista< CompetitionResult > listCompetitions (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de competencias (p. ej.: Mundial de Fútbol 2013) asociada con los mercados seleccionados por el MarketFilter. Actualmente, solo los mercados de fútbol tienen una competencia asociada. | Lista< CompetitionResult > listCompetitions (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de competencias (p. ej.: Mundial de Fútbol 2013) asociada con los mercados seleccionados por el MarketFilter. Actualmente, solo los mercados de fútbol tienen una competencia asociada. | Lista< CompetitionResult > listCompetitions (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de competencias (p. ej.: Mundial de Fútbol 2013) asociada con los mercados seleccionados por el MarketFilter. Actualmente, solo los mercados de fútbol tienen una competencia asociada. | Lista< CompetitionResult > listCompetitions (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de competencias (p. ej.: Mundial de Fútbol 2013) asociada con los mercados seleccionados por el MarketFilter. Actualmente, solo los mercados de fútbol tienen una competencia asociada. | Lista< CompetitionResult > listCompetitions (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de competencias (p. ej.: Mundial de Fútbol 2013) asociada con los mercados seleccionados por el MarketFilter. Actualmente, solo los mercados de fútbol tienen una competencia asociada. |  |
|  | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción |  |
|  | filtro | MarketFilter | MarketFilter |  | El filtro para seleccionar los mercados que desea. Se seleccionan todos los mercados que coincidan con los criterios del filtro. |  |
|  | región | Cadena | Cadena |  | El idioma utilizado para la respuesta. Si no se especifica, 
se devuelve el valor predeterminado. |  |
|  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | Lista< CompetitionResult > | Lista< CompetitionResult > | datos de resultado | datos de resultado |  |  |
|  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| listCountries | listCountries | listCountries | listCountries | listCountries | listCountries | listCountries |
| --- | --- | --- | --- | --- | --- | --- |
|  | Lista< CountryCodeResult > listCountries (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de países asociados con los mercados seleccionados por el MarketFilter. | Lista< CountryCodeResult > listCountries (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de países asociados con los mercados seleccionados por el MarketFilter. | Lista< CountryCodeResult > listCountries (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de países asociados con los mercados seleccionados por el MarketFilter. | Lista< CountryCodeResult > listCountries (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de países asociados con los mercados seleccionados por el MarketFilter. | Lista< CountryCodeResult > listCountries (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de países asociados con los mercados seleccionados por el MarketFilter. |  |
|  | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción |  |
|  | filtro | MarketFilter | MarketFilter |  | El filtro para seleccionar los mercados que desea. Se seleccionan todos los mercados que coincidan con los criterios del filtro. |  |
|  | región | Cadena | Cadena |  | El idioma utilizado para la respuesta. Si no se especifica, 
se devuelve el valor predeterminado. |  |
|  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | Lista< CompetitionResult > | Lista< CompetitionResult > | datos de resultado | datos de resultado |  |  |
|  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| ListCurrentOrders | ListCurrentOrders | ListCurrentOrders | ListCurrentOrders | ListCurrentOrders | ListCurrentOrders | ListCurrentOrders | ListCurrentOrders |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  | listCurrentOrders (Set<String>betIds,Set<String>marketIds, OrderProj ection orderProjection, TimeRange placedDateRange, TimeRange dateRange, OrderBy orderBy, SortDir sortDir,intfromRecord,intrecordCount) muestra APINGException

Devuelve una lista de sus pedidos actuales. Opcionalmente puede filtrar y ordenar sus pedidos actuales mediante la configuración de diversos parámetros, y no establecer ninguno de los parámetros mostrará todos los pedidos en curso hasta un máximo de 1000 apuestas, pedidas como BY_BET y ordenadas como EARLIEST_TO_LATEST. Para recuperar más de 1000 pedidos, debe usar los parámetros fromRecord y recordCount. | listCurrentOrders (Set<String>betIds,Set<String>marketIds, OrderProj ection orderProjection, TimeRange placedDateRange, TimeRange dateRange, OrderBy orderBy, SortDir sortDir,intfromRecord,intrecordCount) muestra APINGException

Devuelve una lista de sus pedidos actuales. Opcionalmente puede filtrar y ordenar sus pedidos actuales mediante la configuración de diversos parámetros, y no establecer ninguno de los parámetros mostrará todos los pedidos en curso hasta un máximo de 1000 apuestas, pedidas como BY_BET y ordenadas como EARLIEST_TO_LATEST. Para recuperar más de 1000 pedidos, debe usar los parámetros fromRecord y recordCount. | listCurrentOrders (Set<String>betIds,Set<String>marketIds, OrderProj ection orderProjection, TimeRange placedDateRange, TimeRange dateRange, OrderBy orderBy, SortDir sortDir,intfromRecord,intrecordCount) muestra APINGException

Devuelve una lista de sus pedidos actuales. Opcionalmente puede filtrar y ordenar sus pedidos actuales mediante la configuración de diversos parámetros, y no establecer ninguno de los parámetros mostrará todos los pedidos en curso hasta un máximo de 1000 apuestas, pedidas como BY_BET y ordenadas como EARLIEST_TO_LATEST. Para recuperar más de 1000 pedidos, debe usar los parámetros fromRecord y recordCount. | listCurrentOrders (Set<String>betIds,Set<String>marketIds, OrderProj ection orderProjection, TimeRange placedDateRange, TimeRange dateRange, OrderBy orderBy, SortDir sortDir,intfromRecord,intrecordCount) muestra APINGException

Devuelve una lista de sus pedidos actuales. Opcionalmente puede filtrar y ordenar sus pedidos actuales mediante la configuración de diversos parámetros, y no establecer ninguno de los parámetros mostrará todos los pedidos en curso hasta un máximo de 1000 apuestas, pedidas como BY_BET y ordenadas como EARLIEST_TO_LATEST. Para recuperar más de 1000 pedidos, debe usar los parámetros fromRecord y recordCount. | listCurrentOrders (Set<String>betIds,Set<String>marketIds, OrderProj ection orderProjection, TimeRange placedDateRange, TimeRange dateRange, OrderBy orderBy, SortDir sortDir,intfromRecord,intrecordCount) muestra APINGException

Devuelve una lista de sus pedidos actuales. Opcionalmente puede filtrar y ordenar sus pedidos actuales mediante la configuración de diversos parámetros, y no establecer ninguno de los parámetros mostrará todos los pedidos en curso hasta un máximo de 1000 apuestas, pedidas como BY_BET y ordenadas como EARLIEST_TO_LATEST. Para recuperar más de 1000 pedidos, debe usar los parámetros fromRecord y recordCount. | listCurrentOrders (Set<String>betIds,Set<String>marketIds, OrderProj ection orderProjection, TimeRange placedDateRange, TimeRange dateRange, OrderBy orderBy, SortDir sortDir,intfromRecord,intrecordCount) muestra APINGException

Devuelve una lista de sus pedidos actuales. Opcionalmente puede filtrar y ordenar sus pedidos actuales mediante la configuración de diversos parámetros, y no establecer ninguno de los parámetros mostrará todos los pedidos en curso hasta un máximo de 1000 apuestas, pedidas como BY_BET y ordenadas como EARLIEST_TO_LATEST. Para recuperar más de 1000 pedidos, debe usar los parámetros fromRecord y recordCount. |  |
|  | Mejores prácticas
Para realizar un seguimiento eficiente de las nuevas coincidencias de apuestas de un momento determinado, los clientes deben utilizar una combinación de dateRange, orderB y “BY_MATCH_TIME” y orderProjection “ALL” para filtrar total o parcialmente los pedidos que coinciden de la lista de apuestas devueltas. La respuesta entonces omite cualquier registro de apuesta que no tenga una fecha coincidente y proporciona una lista de betIds en el orden en el cual coinciden completa o parcialmente según la fecha y la hora especificadas en el campo dateRange. | Mejores prácticas
Para realizar un seguimiento eficiente de las nuevas coincidencias de apuestas de un momento determinado, los clientes deben utilizar una combinación de dateRange, orderB y “BY_MATCH_TIME” y orderProjection “ALL” para filtrar total o parcialmente los pedidos que coinciden de la lista de apuestas devueltas. La respuesta entonces omite cualquier registro de apuesta que no tenga una fecha coincidente y proporciona una lista de betIds en el orden en el cual coinciden completa o parcialmente según la fecha y la hora especificadas en el campo dateRange. | Mejores prácticas
Para realizar un seguimiento eficiente de las nuevas coincidencias de apuestas de un momento determinado, los clientes deben utilizar una combinación de dateRange, orderB y “BY_MATCH_TIME” y orderProjection “ALL” para filtrar total o parcialmente los pedidos que coinciden de la lista de apuestas devueltas. La respuesta entonces omite cualquier registro de apuesta que no tenga una fecha coincidente y proporciona una lista de betIds en el orden en el cual coinciden completa o parcialmente según la fecha y la hora especificadas en el campo dateRange. | Mejores prácticas
Para realizar un seguimiento eficiente de las nuevas coincidencias de apuestas de un momento determinado, los clientes deben utilizar una combinación de dateRange, orderB y “BY_MATCH_TIME” y orderProjection “ALL” para filtrar total o parcialmente los pedidos que coinciden de la lista de apuestas devueltas. La respuesta entonces omite cualquier registro de apuesta que no tenga una fecha coincidente y proporciona una lista de betIds en el orden en el cual coinciden completa o parcialmente según la fecha y la hora especificadas en el campo dateRange. | Mejores prácticas
Para realizar un seguimiento eficiente de las nuevas coincidencias de apuestas de un momento determinado, los clientes deben utilizar una combinación de dateRange, orderB y “BY_MATCH_TIME” y orderProjection “ALL” para filtrar total o parcialmente los pedidos que coinciden de la lista de apuestas devueltas. La respuesta entonces omite cualquier registro de apuesta que no tenga una fecha coincidente y proporciona una lista de betIds en el orden en el cual coinciden completa o parcialmente según la fecha y la hora especificadas en el campo dateRange. | Mejores prácticas
Para realizar un seguimiento eficiente de las nuevas coincidencias de apuestas de un momento determinado, los clientes deben utilizar una combinación de dateRange, orderB y “BY_MATCH_TIME” y orderProjection “ALL” para filtrar total o parcialmente los pedidos que coinciden de la lista de apuestas devueltas. La respuesta entonces omite cualquier registro de apuesta que no tenga una fecha coincidente y proporciona una lista de betIds en el orden en el cual coinciden completa o parcialmente según la fecha y la hora especificadas en el campo dateRange. |  |
|  |  |  |  |  |  |  |  |
|  | Nombre de parámetro | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción |  |
|  | Nombre de parámetro | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción |  |
|  | betIds | betIds | Establecer<String> | Establecer<String> |  | Opcionalmente restringe los resultados a los identificadores de apuesta especificados. Un máximo de 250 betId, o una combinación de 250 betId y marketId está permitida. |  |
|  | marketIds | marketIds | Establecer<String> | Establecer<String> |  | Opcionalmente restringe los resultados a los identificadores de mercado especificados. Un máximo de 250 marketId, o una combinación de 250 betId y marketId está permitida. |  |
|  | orderProjection | orderProjection | OrderProjection | OrderProjection |  | Opcionalmente restringe los resultados según el estado del pedido especificado. |  |
|  | customerOrderRefs | customerOrderRefs | Establecer<CustomerOrderRef> | Establecer<CustomerOrderRef> |  | Opcionalmente restringe los resultados según las referencias especificadas del pedido del cliente. |  |
|  | customerStrategyRefs | customerStrategyRefs | Establecer<CustomerStrategyRef> | Establecer<CustomerStrategyRef> |  | Opcionalmente restringe los resultados según las referencias especificadas de la estrategia del cliente. |  |
|  | dateRange | dateRange | TimeRange | TimeRange |  | Opcionalmente restringe los resultados para que sean desde/hasta la fecha especificada, estas fechas son contextuales a los pedidos devueltos y, por lo tanto, las fechas utilizadas para filtrar cambiarán por las fechas de realización, coincidencia, anulación o asentamiento según el OrderBy. Esta fecha es inclusiva, es decir, si un pedido se realizó exactamente en esa fecha (en milisegundos), entonces se incluirá en los resultados. Si el “desde” es posterior al “hasta”, no se devolverá ningún resultado. |  |
|  | orderBy | orderBy | OrderBy | OrderBy |  | Especifica la forma en que se ordenarán los resultados. Si no pasa ningún valor, el predeterminado es BY_BET. También actúa como un filtro, de manera que solo los pedidos con un valor válido en el campo donde se ordena serán devueltos (es decir, BY_VOID_TIME devuelve solo los pedidos anulados, BY_SETTLED_TIME [se aplica a los mercados parcialmente asentados] devuelve solo los pedidos asentados y BY_MATCH_TIME devuelve solo los pedidos con una fecha coincidente [pedidos anulados, asentados, coincidentes]). Tenga en cuenta que especificar un parámetro orderBy define el contexto del filtro de fecha aplicado por el parámetro dateRange (fecha de realización, coincidencia, anulación o asentamiento). Vea la descripción del parámetro dateRange (arriba) para obtener más información. También vea la definición del tipo OrderBy. |  |
|  | sortDir | sortDir | SortDir | SortDir |  | Especifica la dirección en que se ordenarán los resultados. Si no se pasa ningún valor, el predeterminado es EARLIEST_TO_LATEST. |  |
|  | fromRecord | fromRecord | int | int |  | Especifica el primer registro que se devolverá. Los registros comienzan en el índice cero, no en el índice uno. |  |
|  | recordCount | recordCount | int | int |  | Especifica cuántos registros se devolverán desde la ubicación del índice 'fromRecord'. Tenga en cuenta que existe un límite de tamaño de página de 1000. Un valor de cero indica que quiere todos los registros (desde ‘fromRecord’ y con este valor incluido) hasta el límite. |  |
|  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | CurrentOrderSummaryReport | CurrentOrderSummaryReport | CurrentOrderSummaryReport |  |  |  |  |
|  |  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 |  |
| listClearedOrders | listClearedOrders | listClearedOrders | listClearedOrders | listClearedOrders | listClearedOrders | listClearedOrders | listClearedOrders | listClearedOrders |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | ClearedOrderSummaryReport listClearedOrders (BetStatus betStatus, Set<EventTypeId> eventTypeIds, Set<EventId> eventIds, Set<MarketId> marketIds, Set<RunnerId> runnerIds, Set<BetId> betIds, Side side, TimeRange settledDateRange, Group By groupBy, boolean includeItemDescription, String locale, int fromRecord, int recordCount) muestra APINGException

Devuelve una lista de las apuestas realizadas según el estado de la apuesta, ordenadas por fecha Para recuperar más de 1000 registros, debe usar los parámetros fromRecord y recordCount. De forma predeterminada, el servicio devolverá todos los datos disponibles de los últimos 90 días (vea la nota de Mejores prácticas a continuación). Los campos disponibles en cada acumulación se encuentran aquí | ClearedOrderSummaryReport listClearedOrders (BetStatus betStatus, Set<EventTypeId> eventTypeIds, Set<EventId> eventIds, Set<MarketId> marketIds, Set<RunnerId> runnerIds, Set<BetId> betIds, Side side, TimeRange settledDateRange, Group By groupBy, boolean includeItemDescription, String locale, int fromRecord, int recordCount) muestra APINGException

Devuelve una lista de las apuestas realizadas según el estado de la apuesta, ordenadas por fecha Para recuperar más de 1000 registros, debe usar los parámetros fromRecord y recordCount. De forma predeterminada, el servicio devolverá todos los datos disponibles de los últimos 90 días (vea la nota de Mejores prácticas a continuación). Los campos disponibles en cada acumulación se encuentran aquí | ClearedOrderSummaryReport listClearedOrders (BetStatus betStatus, Set<EventTypeId> eventTypeIds, Set<EventId> eventIds, Set<MarketId> marketIds, Set<RunnerId> runnerIds, Set<BetId> betIds, Side side, TimeRange settledDateRange, Group By groupBy, boolean includeItemDescription, String locale, int fromRecord, int recordCount) muestra APINGException

Devuelve una lista de las apuestas realizadas según el estado de la apuesta, ordenadas por fecha Para recuperar más de 1000 registros, debe usar los parámetros fromRecord y recordCount. De forma predeterminada, el servicio devolverá todos los datos disponibles de los últimos 90 días (vea la nota de Mejores prácticas a continuación). Los campos disponibles en cada acumulación se encuentran aquí | ClearedOrderSummaryReport listClearedOrders (BetStatus betStatus, Set<EventTypeId> eventTypeIds, Set<EventId> eventIds, Set<MarketId> marketIds, Set<RunnerId> runnerIds, Set<BetId> betIds, Side side, TimeRange settledDateRange, Group By groupBy, boolean includeItemDescription, String locale, int fromRecord, int recordCount) muestra APINGException

Devuelve una lista de las apuestas realizadas según el estado de la apuesta, ordenadas por fecha Para recuperar más de 1000 registros, debe usar los parámetros fromRecord y recordCount. De forma predeterminada, el servicio devolverá todos los datos disponibles de los últimos 90 días (vea la nota de Mejores prácticas a continuación). Los campos disponibles en cada acumulación se encuentran aquí | ClearedOrderSummaryReport listClearedOrders (BetStatus betStatus, Set<EventTypeId> eventTypeIds, Set<EventId> eventIds, Set<MarketId> marketIds, Set<RunnerId> runnerIds, Set<BetId> betIds, Side side, TimeRange settledDateRange, Group By groupBy, boolean includeItemDescription, String locale, int fromRecord, int recordCount) muestra APINGException

Devuelve una lista de las apuestas realizadas según el estado de la apuesta, ordenadas por fecha Para recuperar más de 1000 registros, debe usar los parámetros fromRecord y recordCount. De forma predeterminada, el servicio devolverá todos los datos disponibles de los últimos 90 días (vea la nota de Mejores prácticas a continuación). Los campos disponibles en cada acumulación se encuentran aquí | ClearedOrderSummaryReport listClearedOrders (BetStatus betStatus, Set<EventTypeId> eventTypeIds, Set<EventId> eventIds, Set<MarketId> marketIds, Set<RunnerId> runnerIds, Set<BetId> betIds, Side side, TimeRange settledDateRange, Group By groupBy, boolean includeItemDescription, String locale, int fromRecord, int recordCount) muestra APINGException

Devuelve una lista de las apuestas realizadas según el estado de la apuesta, ordenadas por fecha Para recuperar más de 1000 registros, debe usar los parámetros fromRecord y recordCount. De forma predeterminada, el servicio devolverá todos los datos disponibles de los últimos 90 días (vea la nota de Mejores prácticas a continuación). Los campos disponibles en cada acumulación se encuentran aquí | ClearedOrderSummaryReport listClearedOrders (BetStatus betStatus, Set<EventTypeId> eventTypeIds, Set<EventId> eventIds, Set<MarketId> marketIds, Set<RunnerId> runnerIds, Set<BetId> betIds, Side side, TimeRange settledDateRange, Group By groupBy, boolean includeItemDescription, String locale, int fromRecord, int recordCount) muestra APINGException

Devuelve una lista de las apuestas realizadas según el estado de la apuesta, ordenadas por fecha Para recuperar más de 1000 registros, debe usar los parámetros fromRecord y recordCount. De forma predeterminada, el servicio devolverá todos los datos disponibles de los últimos 90 días (vea la nota de Mejores prácticas a continuación). Los campos disponibles en cada acumulación se encuentran aquí |  |
|  | Mejores prácticas
Debe especificar una fecha settledDateRange “desde” al realizar las solicitudes de datos que requieren descarga y mejoran la velocidad de respuesta. Especificar una fecha “Desde” de la última llamada asegurará que solo se devuelvan los datos nuevos. | Mejores prácticas
Debe especificar una fecha settledDateRange “desde” al realizar las solicitudes de datos que requieren descarga y mejoran la velocidad de respuesta. Especificar una fecha “Desde” de la última llamada asegurará que solo se devuelvan los datos nuevos. | Mejores prácticas
Debe especificar una fecha settledDateRange “desde” al realizar las solicitudes de datos que requieren descarga y mejoran la velocidad de respuesta. Especificar una fecha “Desde” de la última llamada asegurará que solo se devuelvan los datos nuevos. | Mejores prácticas
Debe especificar una fecha settledDateRange “desde” al realizar las solicitudes de datos que requieren descarga y mejoran la velocidad de respuesta. Especificar una fecha “Desde” de la última llamada asegurará que solo se devuelvan los datos nuevos. | Mejores prácticas
Debe especificar una fecha settledDateRange “desde” al realizar las solicitudes de datos que requieren descarga y mejoran la velocidad de respuesta. Especificar una fecha “Desde” de la última llamada asegurará que solo se devuelvan los datos nuevos. | Mejores prácticas
Debe especificar una fecha settledDateRange “desde” al realizar las solicitudes de datos que requieren descarga y mejoran la velocidad de respuesta. Especificar una fecha “Desde” de la última llamada asegurará que solo se devuelvan los datos nuevos. | Mejores prácticas
Debe especificar una fecha settledDateRange “desde” al realizar las solicitudes de datos que requieren descarga y mejoran la velocidad de respuesta. Especificar una fecha “Desde” de la última llamada asegurará que solo se devuelvan los datos nuevos. |  |
|  |  |  |  |  |  |  |  |  |
|  | Nombre de parámetro | Nombre de parámetro | Tipo | Tipo | Obligatorio | Obligatorio | Descripción |  |
|  | Nombre de parámetro | Nombre de parámetro | Tipo | Tipo | Obligatorio | Obligatorio | Descripción |  |
|  | betStatus | betStatus | BetStatus | BetStatus |  |  | Restringe los resultados al estado especificado. |  |
|  | eventTypeIds | eventTypeIds | Establecer<EventTypeId> | Establecer<EventTypeId> |  |  | Opcionalmente restringe los resultados a los identificadores de tipo de evento especificados. |  |
|  | eventIds | eventIds | Establecer<EventId> | Establecer<EventId> |  |  | Opcionalmente restringe los resultados a los identificadores de evento especificados. |  |
|  | marketIds | marketIds | Establecer<Market Id> | Establecer<Market Id> |  |  | Opcionalmente restringe los resultados a los identificadores de mercado especificados. |  |
|  | runnerIds | runnerIds | Establecer<RunnerId> | Establecer<RunnerId> |  |  | Opcionalmente restringe los resultados a los corredores especificados. |  |
|  | betIds | betIds | Establecer<BetId> | Establecer<BetId> |  |  | Opcionalmente restringe los resultados a los identificadores de apuesta especificados. |  |
|  | customerOrderRefs | customerOrderRefs | Establecer<CustomerOrderRef> | Establecer<CustomerOrderRef> |  |  | Opcionalmente restringe los resultados según las referencias especificadas del pedido del cliente. |  |
|  | customerStrategyRefs | customerStrategyRefs | Establecer<CustomerStrategyRef> | Establecer<CustomerStrategyRef> |  |  | Opcionalmente restringe los resultados según las referencias especificadas de la estrategia del cliente. |  |
|  | side | side | Side | Side |  |  | Opcionalmente restringe los resultados al lado especificado. |  |
|  | settledDateRange | settledDateRange | TimeRange | TimeRange |  |  | Opcionalmente restringe los resultados para que muestren la fecha de establecimiento especificada desde/hasta. Esta fecha es inclusiva, es decir, si un pedido se efectuó exactamente en esa fecha (en milisegundos), entonces se incluirá en los resultados. Si el “desde” es posterior al “hasta”, no se devolverá ningún resultado. |  |
|  | groupBy | groupBy | GroupBy | GroupBy |  |  | Cómo agregar las líneas, si no se proporcionan, se devuelve el nivel más bajo, es decir, apuesta por apuesta. Esto solo se aplica a SETTLED BetStatus. |  |
|  | includeItemDescription | includeItemDescription | boolean | boolean |  |  | Si es verdadero, entonces se incluye un objeto ItemDescription en la respuesta. |  |
|  | region | region | Cadena | Cadena |  |  | El idioma utilizado para el itemDescription. Si no se especifica, se devuelve el valor predeterminado de la cuenta del cliente. |  |
|  | fromRecord | fromRecord | int | int |  |  | Especifica el primer registro que se devolverá. Los registros comienzan en el índice cero. |  |
|  | recordCount | recordCount | int | int |  |  | Especifica cuántos registros se devolverán desde la ubicación del índice ‘fromRecord’. Tenga en cuenta que existe un límite de tamaño de página de 1000. Un valor de cero indica que quiere todos los registros (desde ‘fromRecord’ y con este valor incluido) hasta el límite. |  |
|  |  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Tipo de retorno | Descripción | Descripción | Descripción |  |  |
|  | CurrentOrderSummaryReport | CurrentOrderSummaryReport | CurrentOrderSummaryReport |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 |  |
| Nivel de acumulación: | BET | SIDE | MARKET | EVENT | EVENT_TYPE | EXCHANGE |
| --- | --- | --- | --- | --- | --- | --- |
| Se establecieron como | S | S | S | S | S | S |
| Fecha de asentamiento | S | MÁX. | MÁX. | MÁX. | MÁX. | MÁX. |
| Recuento de la apuesta | S | S | S | S | S | S |
| Ganancia | S | SUMA | SUMA | SUMA | SUMA | SUMA |
| ID de Exchange | S | S | S | S | S | S |
| ID de tipo de evento | S | S | S | S | S | N |
| ID de evento | S | S | S | S | N | N |
| ID de mercado | S | S | S | N | N | N |
| ID de selección | S | S | N | N | N | N |
| Hándicap | S | S | N | N | N | N |
| Lado | S | S | N | N | N | N |
| Precio solicitado | S | PROM. | N(PROM.) | N | N | N |
| Precio coincidente | S | PROM. | N(PROM.) | N | N | N |
| Tamaño asentado | S | SUMA | N(SUMA) | N | N | N |
| Precio reducido | S | S | S | N | N | N |
| Comisión | N | N | S | SUMA | SUMA | SUMA |
| ID de apuesta | S | N | N | N | N | N |
| Fecha de realización | S | MÁX. | MÁX. | N | N | N |
| Tipo de persistencia | S | S | S | N | N | N |
| Tipo de pedido | S | S | S | N | N | N |
| Código regulador | S | S | S | N | N | N |
| Código de autenticación de regulador | S | S | S | N | N | N |
| Fecha anulada (donde corresponda) | S | MÁX. | MÁX. | N | N | N |
| BetOutcome | S | N | N | N | N | N |
| listEvents | listEvents | listEvents | listEvents | listEvents | listEvents | listEvents |
| --- | --- | --- | --- | --- | --- | --- |
|  | Lista <EventResult > listEvents (MarketFilter filtro, Stringlocale) muestra APINGException
Devuelve una lista de eventos (p. ej.: Reading vs. Man United) asociados con los mercados seleccionados por el MarketFilter. | Lista <EventResult > listEvents (MarketFilter filtro, Stringlocale) muestra APINGException
Devuelve una lista de eventos (p. ej.: Reading vs. Man United) asociados con los mercados seleccionados por el MarketFilter. | Lista <EventResult > listEvents (MarketFilter filtro, Stringlocale) muestra APINGException
Devuelve una lista de eventos (p. ej.: Reading vs. Man United) asociados con los mercados seleccionados por el MarketFilter. | Lista <EventResult > listEvents (MarketFilter filtro, Stringlocale) muestra APINGException
Devuelve una lista de eventos (p. ej.: Reading vs. Man United) asociados con los mercados seleccionados por el MarketFilter. | Lista <EventResult > listEvents (MarketFilter filtro, Stringlocale) muestra APINGException
Devuelve una lista de eventos (p. ej.: Reading vs. Man United) asociados con los mercados seleccionados por el MarketFilter. |  |
|  | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción |  |
|  | filtro | MarketFilter | MarketFilter |  | El filtro para seleccionar los mercados que desea. Se seleccionan todos los mercados que coincidan con los criterios del filtro. |  |
|  | región | Cadena | Cadena |  | El idioma utilizado para la respuesta. Si no se especifica, 
se devuelve el valor predeterminado. |  |
|  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | Lista< EventResult > | Lista< EventResult > | datos de resultado | datos de resultado |  |  |
|  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 |  |
| listEventsTypes | listEventsTypes | listEventsTypes | listEventsTypes | listEventsTypes | listEventsTypes | listEventsTypes |
| --- | --- | --- | --- | --- | --- | --- |
|  | Lista <EventResult > listEvents (MarketFilter filtro, Stringlocale) muestra APINGException
Devuelve una lista de eventos (p. ej.: Reading vs. Man United) asociados con los mercados seleccionados por el MarketFilter. | Lista <EventResult > listEvents (MarketFilter filtro, Stringlocale) muestra APINGException
Devuelve una lista de eventos (p. ej.: Reading vs. Man United) asociados con los mercados seleccionados por el MarketFilter. | Lista <EventResult > listEvents (MarketFilter filtro, Stringlocale) muestra APINGException
Devuelve una lista de eventos (p. ej.: Reading vs. Man United) asociados con los mercados seleccionados por el MarketFilter. | Lista <EventResult > listEvents (MarketFilter filtro, Stringlocale) muestra APINGException
Devuelve una lista de eventos (p. ej.: Reading vs. Man United) asociados con los mercados seleccionados por el MarketFilter. | Lista <EventResult > listEvents (MarketFilter filtro, Stringlocale) muestra APINGException
Devuelve una lista de eventos (p. ej.: Reading vs. Man United) asociados con los mercados seleccionados por el MarketFilter. |  |
|  | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción |  |
|  | filtro | MarketFilter | MarketFilter |  | El filtro para seleccionar los mercados que desea. Se seleccionan todos los mercados que coincidan con los criterios del filtro. |  |
|  | región | Cadena | Cadena |  | El idioma utilizado para la respuesta. Si no se especifica, 
se devuelve el valor predeterminado. |  |
|  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | Lista< EventResult > | Lista< EventResult > | datos de resultado | datos de resultado |  |  |
|  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 |  |
| listMarketBook | listMarketBook | listMarketBook | listMarketBook | listMarketBook | listMarketBook | listMarketBook | listMarketBook | listMarketBook |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | Lista<MarketBook > listMarketBook (List<String>marketIds, PriceProjection priceProjection, OrderP rojection orderProjection, MatchProjection matchProjection, boolean includeOverallPosition, boolean partitionMatchedByStrategyRef, Set<String> customerStrategy
Refs, StringcurrencyCode,Stringlocale, Date matchedSince, Set<BetId> betIds) muestra APINGException

Devuelve una lista de los datos dinámicos de los mercados. Los datos dinámicos incluyen los precios, la situación del mercado, el estado de selecciones, el volumen negociado y el estado de los pedidos que haya realizado en el mercado.

Tenga en cuenta lo siguiente: Las solicitudes por separado deben hacerse para los mercados ABIERTOS y CERRADOS. La solicitud que incluya tanto los mercados ABIERTOS como CERRADOS solo devolverá aquellos mercados que estén ABIERTOS. | Lista<MarketBook > listMarketBook (List<String>marketIds, PriceProjection priceProjection, OrderP rojection orderProjection, MatchProjection matchProjection, boolean includeOverallPosition, boolean partitionMatchedByStrategyRef, Set<String> customerStrategy
Refs, StringcurrencyCode,Stringlocale, Date matchedSince, Set<BetId> betIds) muestra APINGException

Devuelve una lista de los datos dinámicos de los mercados. Los datos dinámicos incluyen los precios, la situación del mercado, el estado de selecciones, el volumen negociado y el estado de los pedidos que haya realizado en el mercado.

Tenga en cuenta lo siguiente: Las solicitudes por separado deben hacerse para los mercados ABIERTOS y CERRADOS. La solicitud que incluya tanto los mercados ABIERTOS como CERRADOS solo devolverá aquellos mercados que estén ABIERTOS. | Lista<MarketBook > listMarketBook (List<String>marketIds, PriceProjection priceProjection, OrderP rojection orderProjection, MatchProjection matchProjection, boolean includeOverallPosition, boolean partitionMatchedByStrategyRef, Set<String> customerStrategy
Refs, StringcurrencyCode,Stringlocale, Date matchedSince, Set<BetId> betIds) muestra APINGException

Devuelve una lista de los datos dinámicos de los mercados. Los datos dinámicos incluyen los precios, la situación del mercado, el estado de selecciones, el volumen negociado y el estado de los pedidos que haya realizado en el mercado.

Tenga en cuenta lo siguiente: Las solicitudes por separado deben hacerse para los mercados ABIERTOS y CERRADOS. La solicitud que incluya tanto los mercados ABIERTOS como CERRADOS solo devolverá aquellos mercados que estén ABIERTOS. | Lista<MarketBook > listMarketBook (List<String>marketIds, PriceProjection priceProjection, OrderP rojection orderProjection, MatchProjection matchProjection, boolean includeOverallPosition, boolean partitionMatchedByStrategyRef, Set<String> customerStrategy
Refs, StringcurrencyCode,Stringlocale, Date matchedSince, Set<BetId> betIds) muestra APINGException

Devuelve una lista de los datos dinámicos de los mercados. Los datos dinámicos incluyen los precios, la situación del mercado, el estado de selecciones, el volumen negociado y el estado de los pedidos que haya realizado en el mercado.

Tenga en cuenta lo siguiente: Las solicitudes por separado deben hacerse para los mercados ABIERTOS y CERRADOS. La solicitud que incluya tanto los mercados ABIERTOS como CERRADOS solo devolverá aquellos mercados que estén ABIERTOS. | Lista<MarketBook > listMarketBook (List<String>marketIds, PriceProjection priceProjection, OrderP rojection orderProjection, MatchProjection matchProjection, boolean includeOverallPosition, boolean partitionMatchedByStrategyRef, Set<String> customerStrategy
Refs, StringcurrencyCode,Stringlocale, Date matchedSince, Set<BetId> betIds) muestra APINGException

Devuelve una lista de los datos dinámicos de los mercados. Los datos dinámicos incluyen los precios, la situación del mercado, el estado de selecciones, el volumen negociado y el estado de los pedidos que haya realizado en el mercado.

Tenga en cuenta lo siguiente: Las solicitudes por separado deben hacerse para los mercados ABIERTOS y CERRADOS. La solicitud que incluya tanto los mercados ABIERTOS como CERRADOS solo devolverá aquellos mercados que estén ABIERTOS. | Lista<MarketBook > listMarketBook (List<String>marketIds, PriceProjection priceProjection, OrderP rojection orderProjection, MatchProjection matchProjection, boolean includeOverallPosition, boolean partitionMatchedByStrategyRef, Set<String> customerStrategy
Refs, StringcurrencyCode,Stringlocale, Date matchedSince, Set<BetId> betIds) muestra APINGException

Devuelve una lista de los datos dinámicos de los mercados. Los datos dinámicos incluyen los precios, la situación del mercado, el estado de selecciones, el volumen negociado y el estado de los pedidos que haya realizado en el mercado.

Tenga en cuenta lo siguiente: Las solicitudes por separado deben hacerse para los mercados ABIERTOS y CERRADOS. La solicitud que incluya tanto los mercados ABIERTOS como CERRADOS solo devolverá aquellos mercados que estén ABIERTOS. | Lista<MarketBook > listMarketBook (List<String>marketIds, PriceProjection priceProjection, OrderP rojection orderProjection, MatchProjection matchProjection, boolean includeOverallPosition, boolean partitionMatchedByStrategyRef, Set<String> customerStrategy
Refs, StringcurrencyCode,Stringlocale, Date matchedSince, Set<BetId> betIds) muestra APINGException

Devuelve una lista de los datos dinámicos de los mercados. Los datos dinámicos incluyen los precios, la situación del mercado, el estado de selecciones, el volumen negociado y el estado de los pedidos que haya realizado en el mercado.

Tenga en cuenta lo siguiente: Las solicitudes por separado deben hacerse para los mercados ABIERTOS y CERRADOS. La solicitud que incluya tanto los mercados ABIERTOS como CERRADOS solo devolverá aquellos mercados que estén ABIERTOS. |  |
|  | Los Límites de solicitud de datos del mercado se aplican a las solicitudes hechas a listMarketBook que incluyen las proyecciones de precio o pedido.

Las llamadas a listMarketBook deben realizarse hasta un máximo de 5 veces por segundo a un solo marketId. | Los Límites de solicitud de datos del mercado se aplican a las solicitudes hechas a listMarketBook que incluyen las proyecciones de precio o pedido.

Las llamadas a listMarketBook deben realizarse hasta un máximo de 5 veces por segundo a un solo marketId. | Los Límites de solicitud de datos del mercado se aplican a las solicitudes hechas a listMarketBook que incluyen las proyecciones de precio o pedido.

Las llamadas a listMarketBook deben realizarse hasta un máximo de 5 veces por segundo a un solo marketId. | Los Límites de solicitud de datos del mercado se aplican a las solicitudes hechas a listMarketBook que incluyen las proyecciones de precio o pedido.

Las llamadas a listMarketBook deben realizarse hasta un máximo de 5 veces por segundo a un solo marketId. | Los Límites de solicitud de datos del mercado se aplican a las solicitudes hechas a listMarketBook que incluyen las proyecciones de precio o pedido.

Las llamadas a listMarketBook deben realizarse hasta un máximo de 5 veces por segundo a un solo marketId. | Los Límites de solicitud de datos del mercado se aplican a las solicitudes hechas a listMarketBook que incluyen las proyecciones de precio o pedido.

Las llamadas a listMarketBook deben realizarse hasta un máximo de 5 veces por segundo a un solo marketId. | Los Límites de solicitud de datos del mercado se aplican a las solicitudes hechas a listMarketBook que incluyen las proyecciones de precio o pedido.

Las llamadas a listMarketBook deben realizarse hasta un máximo de 5 veces por segundo a un solo marketId. |  |
|  |  |  |  |  |  |  |  |  |
|  | Mejores prácticas
Los clientes que deseen usar listMarketBook para obtener precio, volumen, pedidos sin coincidencia (EJECUTABLE) y posición que coincida en una sola operación debe proporcionar una OrderProjection de “EJECUTABLE” en su solicitud de listMarketBook y recibirá todos los pedidos sin coincidencia (EJECUTABLE) y el volumen agregado que coincida de todos los pedidos, independientemente de si coinciden parcial o totalmente. El nivel de adición de volumen que coincide (MatchProjection) solicitado debe ser ROLLED_UP_BY_AVG_PRICE o ROLLED_UP_BY_PRICE, se prefiere el primero. Esto proporciona una sola llamada en la que se puede realizar un seguimiento de los precios, volúmenes negociados, pedidos sin coincidencia y su posición coincidente de evolución con una respuesta de tamaño mínimo y razonablemente fija. | Mejores prácticas
Los clientes que deseen usar listMarketBook para obtener precio, volumen, pedidos sin coincidencia (EJECUTABLE) y posición que coincida en una sola operación debe proporcionar una OrderProjection de “EJECUTABLE” en su solicitud de listMarketBook y recibirá todos los pedidos sin coincidencia (EJECUTABLE) y el volumen agregado que coincida de todos los pedidos, independientemente de si coinciden parcial o totalmente. El nivel de adición de volumen que coincide (MatchProjection) solicitado debe ser ROLLED_UP_BY_AVG_PRICE o ROLLED_UP_BY_PRICE, se prefiere el primero. Esto proporciona una sola llamada en la que se puede realizar un seguimiento de los precios, volúmenes negociados, pedidos sin coincidencia y su posición coincidente de evolución con una respuesta de tamaño mínimo y razonablemente fija. | Mejores prácticas
Los clientes que deseen usar listMarketBook para obtener precio, volumen, pedidos sin coincidencia (EJECUTABLE) y posición que coincida en una sola operación debe proporcionar una OrderProjection de “EJECUTABLE” en su solicitud de listMarketBook y recibirá todos los pedidos sin coincidencia (EJECUTABLE) y el volumen agregado que coincida de todos los pedidos, independientemente de si coinciden parcial o totalmente. El nivel de adición de volumen que coincide (MatchProjection) solicitado debe ser ROLLED_UP_BY_AVG_PRICE o ROLLED_UP_BY_PRICE, se prefiere el primero. Esto proporciona una sola llamada en la que se puede realizar un seguimiento de los precios, volúmenes negociados, pedidos sin coincidencia y su posición coincidente de evolución con una respuesta de tamaño mínimo y razonablemente fija. | Mejores prácticas
Los clientes que deseen usar listMarketBook para obtener precio, volumen, pedidos sin coincidencia (EJECUTABLE) y posición que coincida en una sola operación debe proporcionar una OrderProjection de “EJECUTABLE” en su solicitud de listMarketBook y recibirá todos los pedidos sin coincidencia (EJECUTABLE) y el volumen agregado que coincida de todos los pedidos, independientemente de si coinciden parcial o totalmente. El nivel de adición de volumen que coincide (MatchProjection) solicitado debe ser ROLLED_UP_BY_AVG_PRICE o ROLLED_UP_BY_PRICE, se prefiere el primero. Esto proporciona una sola llamada en la que se puede realizar un seguimiento de los precios, volúmenes negociados, pedidos sin coincidencia y su posición coincidente de evolución con una respuesta de tamaño mínimo y razonablemente fija. | Mejores prácticas
Los clientes que deseen usar listMarketBook para obtener precio, volumen, pedidos sin coincidencia (EJECUTABLE) y posición que coincida en una sola operación debe proporcionar una OrderProjection de “EJECUTABLE” en su solicitud de listMarketBook y recibirá todos los pedidos sin coincidencia (EJECUTABLE) y el volumen agregado que coincida de todos los pedidos, independientemente de si coinciden parcial o totalmente. El nivel de adición de volumen que coincide (MatchProjection) solicitado debe ser ROLLED_UP_BY_AVG_PRICE o ROLLED_UP_BY_PRICE, se prefiere el primero. Esto proporciona una sola llamada en la que se puede realizar un seguimiento de los precios, volúmenes negociados, pedidos sin coincidencia y su posición coincidente de evolución con una respuesta de tamaño mínimo y razonablemente fija. | Mejores prácticas
Los clientes que deseen usar listMarketBook para obtener precio, volumen, pedidos sin coincidencia (EJECUTABLE) y posición que coincida en una sola operación debe proporcionar una OrderProjection de “EJECUTABLE” en su solicitud de listMarketBook y recibirá todos los pedidos sin coincidencia (EJECUTABLE) y el volumen agregado que coincida de todos los pedidos, independientemente de si coinciden parcial o totalmente. El nivel de adición de volumen que coincide (MatchProjection) solicitado debe ser ROLLED_UP_BY_AVG_PRICE o ROLLED_UP_BY_PRICE, se prefiere el primero. Esto proporciona una sola llamada en la que se puede realizar un seguimiento de los precios, volúmenes negociados, pedidos sin coincidencia y su posición coincidente de evolución con una respuesta de tamaño mínimo y razonablemente fija. | Mejores prácticas
Los clientes que deseen usar listMarketBook para obtener precio, volumen, pedidos sin coincidencia (EJECUTABLE) y posición que coincida en una sola operación debe proporcionar una OrderProjection de “EJECUTABLE” en su solicitud de listMarketBook y recibirá todos los pedidos sin coincidencia (EJECUTABLE) y el volumen agregado que coincida de todos los pedidos, independientemente de si coinciden parcial o totalmente. El nivel de adición de volumen que coincide (MatchProjection) solicitado debe ser ROLLED_UP_BY_AVG_PRICE o ROLLED_UP_BY_PRICE, se prefiere el primero. Esto proporciona una sola llamada en la que se puede realizar un seguimiento de los precios, volúmenes negociados, pedidos sin coincidencia y su posición coincidente de evolución con una respuesta de tamaño mínimo y razonablemente fija. |  |
|  |  |  |  |  |  |  |  |  |
|  | Nombre de parámetro | Nombre de parámetro | Tipo | Tipo | Tipo | Obligatorio | Descripción |  |
|  | Nombre de parámetro | Nombre de parámetro | Tipo | Tipo | Tipo | Obligatorio | Descripción |  |
|  | marketIds | marketIds | Lista<String> | Lista<String> | Lista<String> |  | Uno o más identificadores de mercado. El número de mercados devuelto depende de la cantidad de datos que solicite a través de la proyección de precios. |  |
|  | priceProjection | priceProjection | PriceProjection | PriceProjection | PriceProjection |  | La proyección de los datos de precios que desea recibir en la respuesta. |  |
|  | orderProjection | orderProjection | OrderProjection | OrderProjection | OrderProjection |  | Los pedidos que desea recibir en la respuesta. |  |
|  | matchProjection | matchProjection | MatchProjection | MatchProjection | MatchProjection |  | Si solicita pedidos, especifique la representación de las coincidencias. |  |
|  | includeOverallPosition | includeOverallPosition | boolean | boolean | boolean |  | Si solicita pedidos, se devuelven coincidencias para cada selección. Si no se especifica, el valor predeterminado es verdadero. |  |
|  | partitionMatchedByStrategyRef | partitionMatchedByStrategyRef | boolean | boolean | boolean |  | Si solicita pedidos, se devuelve el desglose de las coincidencias por estrategia para cada selección. Si no se especifica, el valor predeterminado es falso. |  |
|  | customerStrategyRefs | customerStrategyRefs | Establecer<String> | Establecer<String> | Establecer<String> |  | Si solicita pedidos, restringe los resultados a los pedidos que coincidan con alguno de los conjuntos especificados de estrategias definidas por el cliente.
También filtra qué coincidencias por estrategia para las selecciones se devuelven, si partitionMatchedByStrategyRef es verdadero.
Un conjunto vacío se tratará como si el parámetro se hubiera omitido (o pasa nulo). |  |
|  | currencyCode | currencyCode | Cadena | Cadena | Cadena |  | Un código de moneda estándar de Betfair. Si no se especifica, se usa el código de moneda predeterminado. |  |
|  | region | region | Cadena | Cadena | Cadena |  | El idioma utilizado para la respuesta. Si no se especifica, se devuelve el valor predeterminado. |  |
|  | matchedSince | matchedSince | Fecha | Fecha | Fecha |  | Si solicita pedidos, restringe los resultados a los pedidos que tienen, al menos, un fragmento que coincide desde la fecha especificada (se devolverán todos los fragmentos coincidentes de tal pedido, incluso si algunos coinciden antes de la fecha especificada).
Todos los pedidos EJECUTABLES serán devueltos, independientemente de la fecha coincidente. |  |
|  | betIds | betIds | Establecer<BetId> | Establecer<BetId> | Establecer<BetId> |  | Si solicita pedidos, restringe los resultados a los pedidos con el ID de apuesta especificado. |  |
|  |  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |  |  |
|  | Lista< MarketBook > | Lista< MarketBook > | datos de resultado | datos de resultado |  |  |  |  |
|  |  |  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 |  |
| Nombre de parámetro | Tipo | Obligatorio | Descripción |
| --- | --- | --- | --- |
| marketId | MarketId |  | El identificador único para el mercado. |
| selectionId | SelectionId |  | El identificador único para la selección en el mercado. |
| handicap | double |  | La proyección de los datos de precios que desea recibir en la respuesta. |
| priceProjection | PriceProjection |  | La proyección de los datos de precios que desea recibir en la respuesta. |
| orderProjection | OrderProjection |  | Los pedidos que desea recibir en la respuesta. |
| matchProjection | MatchProjection |  | Si solicita pedidos, especifique la representación de las coincidencias. |
| includeOverallPosition | boolean |  | Si solicita pedidos, se devuelven coincidencias para cada selección. Si no se especifica, el valor predeterminado es verdadero. |
| Partition MatchedByStrategyRef | boolean |  | Si solicita pedidos, se devuelve el desglose de las coincidencias por estrategia para cada selección. Si no se especifica, el valor predeterminado es falso. |
| customerStrategyRefs | Establecer<String> |  | Si solicita pedidos, restringe los resultados a los pedidos que coincidan con alguno de los conjuntos especificados de estrategias definidas por el cliente.
También filtra qué coincidencias por estrategia para las selecciones se devuelven, si partitionMatchedByStrategyRef es verdadero.
Un conjunto vacío se tratará como si el parámetro se hubiera omitido (o pasa nulo). |
| currencyCode | Cadena |  | Un código de moneda estándar de Betfair. Si no se especifica, se usa el código de moneda predeterminado. |
| región | Cadena |  | El idioma utilizado para la respuesta. Si no se especifica, se devuelve el valor predeterminado. |
| matchedSince | Fecha |  | Si solicita pedidos, restringe los resultados a los pedidos que tienen al menos un fragmento que coincide desde
la fecha especificada (todos los fragmentos coincidentes de tal pedido se devolverán, aunque algunos hayan coincidido antes de la fecha especificada).
Todos los pedidos EJECUTABLES serán devueltos, independientemente de la fecha coincidente. |
| betIds | Establecer<BetId> |  | Si solicita pedidos, restringe los resultados a los pedidos con el ID de apuesta especificado. |
| Tipo de retorno | Descripción |
| --- | --- |
| Lista< MarketBook > | datos de resultado |
| Muestra | Descripción |
| --- | --- |
| APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. |
| listMarketCatalogue | listMarketCatalogue | listMarketCatalogue | listMarketCatalogue | listMarketCatalogue | listMarketCatalogue | listMarketCatalogue |
| --- | --- | --- | --- | --- | --- | --- |
|  | Lista< MarketCatalogue > listMarketCatalogue ( MarketFilter filtro ,Set< MarketProjection >marketProj ection, MarketSort sort, intmaxResults ,Stringlocale ) muestra APINGException
Devuelve una lista de la información acerca de los mercados publicados (ACTIVO/SUSPENDIDO) que no cambia (o cambia muy raramente). Utilice listMarketCatalogue para recuperar el nombre del mercado, los nombres de las selecciones y otra información sobre los mercados. Límites de solicitud de datos del mercado se aplica a las solicitudes hechas a listMarketCatalogue.

Tenga en cuenta lo siguiente: listMarketCatalogue no devuelve los mercados que están cerrados. | Lista< MarketCatalogue > listMarketCatalogue ( MarketFilter filtro ,Set< MarketProjection >marketProj ection, MarketSort sort, intmaxResults ,Stringlocale ) muestra APINGException
Devuelve una lista de la información acerca de los mercados publicados (ACTIVO/SUSPENDIDO) que no cambia (o cambia muy raramente). Utilice listMarketCatalogue para recuperar el nombre del mercado, los nombres de las selecciones y otra información sobre los mercados. Límites de solicitud de datos del mercado se aplica a las solicitudes hechas a listMarketCatalogue.

Tenga en cuenta lo siguiente: listMarketCatalogue no devuelve los mercados que están cerrados. | Lista< MarketCatalogue > listMarketCatalogue ( MarketFilter filtro ,Set< MarketProjection >marketProj ection, MarketSort sort, intmaxResults ,Stringlocale ) muestra APINGException
Devuelve una lista de la información acerca de los mercados publicados (ACTIVO/SUSPENDIDO) que no cambia (o cambia muy raramente). Utilice listMarketCatalogue para recuperar el nombre del mercado, los nombres de las selecciones y otra información sobre los mercados. Límites de solicitud de datos del mercado se aplica a las solicitudes hechas a listMarketCatalogue.

Tenga en cuenta lo siguiente: listMarketCatalogue no devuelve los mercados que están cerrados. | Lista< MarketCatalogue > listMarketCatalogue ( MarketFilter filtro ,Set< MarketProjection >marketProj ection, MarketSort sort, intmaxResults ,Stringlocale ) muestra APINGException
Devuelve una lista de la información acerca de los mercados publicados (ACTIVO/SUSPENDIDO) que no cambia (o cambia muy raramente). Utilice listMarketCatalogue para recuperar el nombre del mercado, los nombres de las selecciones y otra información sobre los mercados. Límites de solicitud de datos del mercado se aplica a las solicitudes hechas a listMarketCatalogue.

Tenga en cuenta lo siguiente: listMarketCatalogue no devuelve los mercados que están cerrados. | Lista< MarketCatalogue > listMarketCatalogue ( MarketFilter filtro ,Set< MarketProjection >marketProj ection, MarketSort sort, intmaxResults ,Stringlocale ) muestra APINGException
Devuelve una lista de la información acerca de los mercados publicados (ACTIVO/SUSPENDIDO) que no cambia (o cambia muy raramente). Utilice listMarketCatalogue para recuperar el nombre del mercado, los nombres de las selecciones y otra información sobre los mercados. Límites de solicitud de datos del mercado se aplica a las solicitudes hechas a listMarketCatalogue.

Tenga en cuenta lo siguiente: listMarketCatalogue no devuelve los mercados que están cerrados. |  |
|  | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción |  |
|  | filtro | MarketFilter | MarketFilter |  | El filtro para seleccionar los mercados que desea. Se seleccionan todos los mercados que coincidan con los criterios del filtro. |  |
|  | región | Cadena | Cadena |  | El idioma utilizado para la respuesta. Si no se especifica, se devuelve el valor predeterminado. |  |
|  | sort | MarketSort | MarketSort |  | El orden de los resultados. Se utilizará de forma predeterminada RANK si no pasa. RANK es una prioridad que está determinado por nuestro equipo de operaciones de mercado en el sistema de administración. Una clasificación general del resultado se deriva de la clasificación dada a los atributos de flujo para el resultado. EventType, Competition, StartTime, MarketType, MarketId. Por ejemplo, EventType es clasificado por los deportes más populares y marketTypes se clasifican en el orden siguiente: ODDS ASIAN LINE RANGE Si todas las demás dimensiones del resultado son iguales, entonces los resultados se clasifican en el orden MarketId. |  |
|  | maxResults | int | int |  | El límite en el número total de resultados devueltos debe ser mayor que 0 y menor o igual a 1000 |  |
|  | región | Cadena | Cadena |  | El idioma utilizado para la respuesta. Si no se especifica, se devuelve el valor predeterminado. |  |
|  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | Lista< CompetitionResult > | Lista< CompetitionResult > | datos de resultado | datos de resultado |  |  |
|  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| Parámetro | Descripción | Ejemplo |
| --- | --- | --- |
| WEIGHT_UNITS | La unidad de peso utilizada | libras |
| ADJUSTED_RATING | Las calificaciones ajustadas son las clasificaciones específicas de una carrera que reflejan los pesos asignados en la carrera y, en algunas circunstancias, la edad del caballo. En su conjunto, representan la oportunidad que tiene cada corredor en el formulario. https://www.timeform.com/Racing/Articles/How_the_ ratings_for_a_race_are_calculated | 79 |
| DAM_YEAR_BORN | El año del nacimiento de la madre del caballo | 1997 |
| DAYS_SINCE_LAST_RUN | El número de días desde la última vez que corrió el caballo | 66 |
| WEARING | Cualquier equipo adicional que use el caballo | correa para lengua |
| DAMSIRE_YEAR_BORN | El año en el que nació el abuelo materno del caballo | 1988 |
| SIRE_BRED | El país donde se crió el padre del caballo | IRE |
| TRAINER_NAME | El nombre del entrenador del caballo | Fergal O'Brien |
| STALL_DRAW | El número del puesto desde donde comienza el caballo | 10 |
| SEX_TYPE | El sexo del caballo | f |
| OWNER_NAME | El propietario del caballo | Sr. M. C. Fahy |
| SIRE_NAME | El nombre del padre del caballo | Revoque |
| FORECASTPRICE_NUMERATOR | El numerador del precio del pronóstico | 13 |
| FORECASTPRICE_DENOMINATOR | El denominador del precio del pronóstico | 8 |
| JOCKEY_CLAIM | La reducción en el peso que lleva el caballo para un jinete particular | 5 |
| WEIGHT_VALUE | El peso del caballo | 163 |
| DAM_NAME | El nombre de la madre del caballo | Rare Gesture |
| AGE | La edad del caballo | 7 |
| COLOUR_TYPE | El color del caballo | b |
| DAMSIRE_BRED | El país donde nació el abuelo del caballo | IRE |
| DAMSIRE_NAME | El nombre del abuelo del caballo | Shalford |
| SIRE_YEAR_BORN | El año en que nació el padre del caballo | 1994 |
| OFFICIAL_RATING | La clasificación oficial del caballo | 97 |
| FORM | El reciente formulario del caballo | 212246 |
| BRED | El país en el que nació el caballo | IRE |
| runnerId | El runnerId para el caballo | 62434983 |
| JOCKEY_NAME | El nombre del jockey. Tenga en cuenta lo siguiente: Este campo contendrá la palabra ‘Reserva’ en caso de que el caballo se haya introducido en el mercado como un corredor de reserva. Cualquier corredor de reserva se retirará del mercado una vez que se haya confirmado que no correrá. | Paddy Brenna |
| DAM_BRED | El país donde nació la madre del caballo | IRE |
| COLOURS_DESCRIPTION | La descripción textual de la vestimenta del jinete | Mangas azul real y blancas |
| COLOURS_FILENAME | Una dirección URL relacionada con un archivo de imagen correspondiente a la vestimenta del jinete Debe agregar el valor de este campo a la URL base: http://content-cache.betfair.com/feeds_images/Hors es/SilkColours/ | c20140225lei/0 |
| CLOTH_NUMBER | El número en la tela de la silla | 5 |
| CLOTH_NUMBER ALPHA | El número en la tela de la silla En las carreras de EE. UU., donde el corredor tiene una pareja, este campo mostrará el número en la tela de la pareja del corredor, por ejemplo "1A" |  |
| listMarketProfitAndLoss | listMarketProfitAndLoss | listMarketProfitAndLoss | listMarketProfitAndLoss | listMarketProfitAndLoss | listMarketProfitAndLoss | listMarketProfitAndLoss |
| --- | --- | --- | --- | --- | --- | --- |
|  | Lista<MarketProfitAndLoss> listMarketProfitAndLoss ( Set<MarketId> marketIds, boolean includeSettledBets, boolean includeBspBets, boolean netOfCommission ) muestra APINGException

Recupera pérdidas y ganancias para una lista determinada de mercados abiertos. Los valores se calculan usando apuestas que coincidan y opcionalmente apuestas realizadas Solo se implementan los mercados de probabilidades (MarketBettingType = ODDS), los mercados de otros tipos se ignoran en silencio.

Para recuperar sus ganancias y pérdidas para los mercados CERRADOS, utilice la solicitud listClearedOrders.
Tenga en cuenta lo siguiente: Los Límites de solicitud de datos del mercado se aplican a las solicitudes hechas a listMarketProfitAndLoss | Lista<MarketProfitAndLoss> listMarketProfitAndLoss ( Set<MarketId> marketIds, boolean includeSettledBets, boolean includeBspBets, boolean netOfCommission ) muestra APINGException

Recupera pérdidas y ganancias para una lista determinada de mercados abiertos. Los valores se calculan usando apuestas que coincidan y opcionalmente apuestas realizadas Solo se implementan los mercados de probabilidades (MarketBettingType = ODDS), los mercados de otros tipos se ignoran en silencio.

Para recuperar sus ganancias y pérdidas para los mercados CERRADOS, utilice la solicitud listClearedOrders.
Tenga en cuenta lo siguiente: Los Límites de solicitud de datos del mercado se aplican a las solicitudes hechas a listMarketProfitAndLoss | Lista<MarketProfitAndLoss> listMarketProfitAndLoss ( Set<MarketId> marketIds, boolean includeSettledBets, boolean includeBspBets, boolean netOfCommission ) muestra APINGException

Recupera pérdidas y ganancias para una lista determinada de mercados abiertos. Los valores se calculan usando apuestas que coincidan y opcionalmente apuestas realizadas Solo se implementan los mercados de probabilidades (MarketBettingType = ODDS), los mercados de otros tipos se ignoran en silencio.

Para recuperar sus ganancias y pérdidas para los mercados CERRADOS, utilice la solicitud listClearedOrders.
Tenga en cuenta lo siguiente: Los Límites de solicitud de datos del mercado se aplican a las solicitudes hechas a listMarketProfitAndLoss | Lista<MarketProfitAndLoss> listMarketProfitAndLoss ( Set<MarketId> marketIds, boolean includeSettledBets, boolean includeBspBets, boolean netOfCommission ) muestra APINGException

Recupera pérdidas y ganancias para una lista determinada de mercados abiertos. Los valores se calculan usando apuestas que coincidan y opcionalmente apuestas realizadas Solo se implementan los mercados de probabilidades (MarketBettingType = ODDS), los mercados de otros tipos se ignoran en silencio.

Para recuperar sus ganancias y pérdidas para los mercados CERRADOS, utilice la solicitud listClearedOrders.
Tenga en cuenta lo siguiente: Los Límites de solicitud de datos del mercado se aplican a las solicitudes hechas a listMarketProfitAndLoss | Lista<MarketProfitAndLoss> listMarketProfitAndLoss ( Set<MarketId> marketIds, boolean includeSettledBets, boolean includeBspBets, boolean netOfCommission ) muestra APINGException

Recupera pérdidas y ganancias para una lista determinada de mercados abiertos. Los valores se calculan usando apuestas que coincidan y opcionalmente apuestas realizadas Solo se implementan los mercados de probabilidades (MarketBettingType = ODDS), los mercados de otros tipos se ignoran en silencio.

Para recuperar sus ganancias y pérdidas para los mercados CERRADOS, utilice la solicitud listClearedOrders.
Tenga en cuenta lo siguiente: Los Límites de solicitud de datos del mercado se aplican a las solicitudes hechas a listMarketProfitAndLoss |  |
|  | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción |  |
|  | marketIds | Establecer<MarketId> | Establecer<MarketId> |  | Lista de mercados para calcular ganancias y pérdidas |  |
|  | includeSettledBets | boolean | boolean |  | Opción para incluir las apuestas realizadas (solo mercados parcialmente asentados). El valor predeterminado es falso si no se ha especificado. |  |
|  | includeBspBets | boolean | boolean |  | Opción para incluir las apuestas de BSP. El valor predeterminado es falso si no se ha especificado. |  |
|  | netOfCommission | boolean | boolean |  | Opción para devolver el neto de pérdidas y ganancias de la tasa de comisión actual de los usuarios para este mercado, incluidas las tarifas especiales. El valor predeterminado es falso si no se ha especificado. |  |
|  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | Lista<MarketProfitAndLoss> | Lista<MarketProfitAndLoss> |  |  |  |  |
|  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| listMarketTypes | listMarketTypes | listMarketTypes | listMarketTypes | listMarketTypes | listMarketTypes | listMarketTypes |
| --- | --- | --- | --- | --- | --- | --- |
|  | Lista< MarketTypeResult > listMarketTypes ( MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de los tipos de mercado (p. ej. MATCH_ODDS, NEXT_META) asociados con los mercados seleccionados por MarketFilter. Los tipos de mercado son siempre los mismos, independientemente de la configuración regional. | Lista< MarketTypeResult > listMarketTypes ( MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de los tipos de mercado (p. ej. MATCH_ODDS, NEXT_META) asociados con los mercados seleccionados por MarketFilter. Los tipos de mercado son siempre los mismos, independientemente de la configuración regional. | Lista< MarketTypeResult > listMarketTypes ( MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de los tipos de mercado (p. ej. MATCH_ODDS, NEXT_META) asociados con los mercados seleccionados por MarketFilter. Los tipos de mercado son siempre los mismos, independientemente de la configuración regional. | Lista< MarketTypeResult > listMarketTypes ( MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de los tipos de mercado (p. ej. MATCH_ODDS, NEXT_META) asociados con los mercados seleccionados por MarketFilter. Los tipos de mercado son siempre los mismos, independientemente de la configuración regional. | Lista< MarketTypeResult > listMarketTypes ( MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de los tipos de mercado (p. ej. MATCH_ODDS, NEXT_META) asociados con los mercados seleccionados por MarketFilter. Los tipos de mercado son siempre los mismos, independientemente de la configuración regional. |  |
|  | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción |  |
|  | filtro | MarketFilter | MarketFilter |  | El filtro para seleccionar los mercados que desea. Se seleccionan todos los mercados que coincidan con los criterios del filtro. |  |
|  | región | Cadena | Cadena |  | El idioma utilizado para la respuesta. Si no se especifica, 
se devuelve el valor predeterminado. |  |
|  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | Lista< MarketTypeResult > | Lista< MarketTypeResult > | datos de resultado | datos de resultado |  |  |
|  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| listTimeRanges | listTimeRanges | listTimeRanges | listTimeRanges | listTimeRanges | listTimeRanges | listTimeRanges |
| --- | --- | --- | --- | --- | --- | --- |
|  | Lista< TimeRangeResult > listTimeRanges (MarketFilter filtro, TimeGranularity granularity) muestra APINGException

Devuelve una lista de rangos de tiempo en la granularidad especificada en la solicitud (p. ej.: de 3 p.m. a 4 p.m., del 14 de agosto al 15 de agosto) asociada con los mercados seleccionados por el MarketFilter. | Lista< TimeRangeResult > listTimeRanges (MarketFilter filtro, TimeGranularity granularity) muestra APINGException

Devuelve una lista de rangos de tiempo en la granularidad especificada en la solicitud (p. ej.: de 3 p.m. a 4 p.m., del 14 de agosto al 15 de agosto) asociada con los mercados seleccionados por el MarketFilter. | Lista< TimeRangeResult > listTimeRanges (MarketFilter filtro, TimeGranularity granularity) muestra APINGException

Devuelve una lista de rangos de tiempo en la granularidad especificada en la solicitud (p. ej.: de 3 p.m. a 4 p.m., del 14 de agosto al 15 de agosto) asociada con los mercados seleccionados por el MarketFilter. | Lista< TimeRangeResult > listTimeRanges (MarketFilter filtro, TimeGranularity granularity) muestra APINGException

Devuelve una lista de rangos de tiempo en la granularidad especificada en la solicitud (p. ej.: de 3 p.m. a 4 p.m., del 14 de agosto al 15 de agosto) asociada con los mercados seleccionados por el MarketFilter. | Lista< TimeRangeResult > listTimeRanges (MarketFilter filtro, TimeGranularity granularity) muestra APINGException

Devuelve una lista de rangos de tiempo en la granularidad especificada en la solicitud (p. ej.: de 3 p.m. a 4 p.m., del 14 de agosto al 15 de agosto) asociada con los mercados seleccionados por el MarketFilter. |  |
|  | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción |  |
|  | filtro | MarketFilter | MarketFilter |  | El filtro para seleccionar los mercados que desea. Se seleccionan todos los mercados que coincidan con los criterios del filtro. |  |
|  | granularity | TimeGranularity | TimeGranularity |  | La granularidad de los períodos que corresponden a los mercados seleccionados por el filtro del mercado. |  |
|  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | Lista< TimeRangeResult > | Lista< TimeRangeResult > | datos de resultado | datos de resultado |  |  |
|  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| listVenues | listVenues | listVenues | listVenues | listVenues | listVenues | listVenues |
| --- | --- | --- | --- | --- | --- | --- |
|  | Lista< VenueResult > listVenues (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de lugares (p. ej.: Cheltenham, Ascot) asociados con los mercados seleccionados por el MarketFilter. Actualmente, solo los mercados de carreras de caballos se asocian con una sede. | Lista< VenueResult > listVenues (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de lugares (p. ej.: Cheltenham, Ascot) asociados con los mercados seleccionados por el MarketFilter. Actualmente, solo los mercados de carreras de caballos se asocian con una sede. | Lista< VenueResult > listVenues (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de lugares (p. ej.: Cheltenham, Ascot) asociados con los mercados seleccionados por el MarketFilter. Actualmente, solo los mercados de carreras de caballos se asocian con una sede. | Lista< VenueResult > listVenues (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de lugares (p. ej.: Cheltenham, Ascot) asociados con los mercados seleccionados por el MarketFilter. Actualmente, solo los mercados de carreras de caballos se asocian con una sede. | Lista< VenueResult > listVenues (MarketFilter filtro, Stringlocale) muestra APINGException

Devuelve una lista de lugares (p. ej.: Cheltenham, Ascot) asociados con los mercados seleccionados por el MarketFilter. Actualmente, solo los mercados de carreras de caballos se asocian con una sede. |  |
|  | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción |  |
|  | filtro | MarketFilter | MarketFilter |  | El filtro para seleccionar los mercados que desea. Se seleccionan todos los mercados que coincidan con los criterios del filtro. |  |
|  | región | Cadena | Cadena |  | El idioma utilizado para la respuesta. Si no se especifica, se devuelve el valor predeterminado. |  |
|  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | Lista< VenueResult > | Lista< VenueResult > | datos de resultado | datos de resultado |  |  |
|  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| placeOrders | placeOrders | placeOrders | placeOrders | placeOrders | placeOrders | placeOrders |
| --- | --- | --- | --- | --- | --- | --- |
|  | PlaceExecutionReport placeOrders (StringmarketId, Lista< PlaceInstruction >instructions, String customerRef, MarketVersion marketVersion, String customerStrategyRef, boolean async) muestra APINGException

Colocar nuevas órdenes en el mercado. Esta operación es atómica, ya que se colocan todas las órdenes o no se coloca ninguna. Tenga en cuenta que se aplican reglas de tamaño de apuestas adicionales en el Exchange italiano. | PlaceExecutionReport placeOrders (StringmarketId, Lista< PlaceInstruction >instructions, String customerRef, MarketVersion marketVersion, String customerStrategyRef, boolean async) muestra APINGException

Colocar nuevas órdenes en el mercado. Esta operación es atómica, ya que se colocan todas las órdenes o no se coloca ninguna. Tenga en cuenta que se aplican reglas de tamaño de apuestas adicionales en el Exchange italiano. | PlaceExecutionReport placeOrders (StringmarketId, Lista< PlaceInstruction >instructions, String customerRef, MarketVersion marketVersion, String customerStrategyRef, boolean async) muestra APINGException

Colocar nuevas órdenes en el mercado. Esta operación es atómica, ya que se colocan todas las órdenes o no se coloca ninguna. Tenga en cuenta que se aplican reglas de tamaño de apuestas adicionales en el Exchange italiano. | PlaceExecutionReport placeOrders (StringmarketId, Lista< PlaceInstruction >instructions, String customerRef, MarketVersion marketVersion, String customerStrategyRef, boolean async) muestra APINGException

Colocar nuevas órdenes en el mercado. Esta operación es atómica, ya que se colocan todas las órdenes o no se coloca ninguna. Tenga en cuenta que se aplican reglas de tamaño de apuestas adicionales en el Exchange italiano. | PlaceExecutionReport placeOrders (StringmarketId, Lista< PlaceInstruction >instructions, String customerRef, MarketVersion marketVersion, String customerStrategyRef, boolean async) muestra APINGException

Colocar nuevas órdenes en el mercado. Esta operación es atómica, ya que se colocan todas las órdenes o no se coloca ninguna. Tenga en cuenta que se aplican reglas de tamaño de apuestas adicionales en el Exchange italiano. |  |
|  | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción |  |
|  | marketId | Cadena | Cadena |  | El ID del mercado en el que se harán estas órdenes |  |
|  | instructions | Lista< PlaceInstruction > | Lista< PlaceInstruction > |  | El número de instrucciones de colocación. El límite de instrucciones de colocación por solicitud es de 200 para el Exchange de Reino Unido/Australia y 50 para el Exchange italiano. |  |
|  | customerRef | Cadena | Cadena |  | Parámetro opcional que permite al cliente pasar una cadena única (hasta 32 caracteres) que se utiliza para desduplicar nuevos envíos confundidos. CustomerRef puede contener: caracteres en mayúscula/minúscula, dígitos, caracteres : - . _ + * : ; ~ únicamente. Tenga en cuenta lo siguiente: Existe una ventana de tiempo asociada con la desduplicación de envíos duplicados que es de 60 segundos. |  |
|  | marketVersion | MarketVersion | MarketVersion |  | Parámetro opcional que permite al cliente especificar en qué versión del mercado
se deben hacer los pedidos. Si la versión actual del mercado es mayor que la enviada en un pedido,
la apuesta habrá caducado. |  |
|  | customerStrategyRef | Cadena | Cadena |  | Una referencia opcional que pueden usar los clientes para especificar qué estrategia ha enviado el pedido.
La referencia se devolverá en mensajes de cambio de pedidos a través de la API de secuencia. La cadena se
limita a 15 caracteres. Si se proporciona una cadena vacía, se considerará nula. |  |
|  | async | boolean | boolean |  | Un marcador opcional (ningún ajuste equivale a falso) que especifica si los pedidos deben colocarse de forma asincrónica. Los pedidos se pueden rastrear a través de la API de secuencia de Exchange o la API-NG al proporcionar customerOrderRef para cada pedido de colocación.
El estado de un pedido estará PENDIENTE y no se devolverá ningún ID de apuesta.
Esta funcionalidad está disponible para todos los tipos de apuestas, incluidos Mercado en el cierre y Límite en el cierre |  |
|  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | PlaceExecutionReport | PlaceExecutionReport |  |  |  |  |
|  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
|  | Versión del mercado | Versión mínima para no ser rechazada | Comportamiento esperado |
| --- | --- | --- | --- |
| Mercado activado | 1234 | 1234 |  |
| Hora de inicio actualizada 
(mercado no suspendido) | 1235 | 1234 | No hay cambio de material, las apuestas realizadas antes del cambio pero recibidas después se procesarán normalmente |
| Corredor eliminado (en suspensión) | 1236 | 1236 | Cambio de material, las apuestas realizadas antes del cambio pero recibidas después serán rechazadas |
| Mercado cambiado en el juego | 1237 | 1237 | Como anteriormente |
| Tipo de carrera | Número de corredores(1) | Número de plazas | Fracción de probabilidades de ganar “divisor Each-Way" |
| --- | --- | --- | --- |
| Hándicap | 16 o más | 4 | 1/4 |
| Hándicap | De 12 a 15 | 3 | 1/4 |
| Hándicap | De 8 a 11 | 3 | 1/5 |
| Hándicap | De 5 a 7 | 2 | 1/4 |
| No hándicap | 8 o más | 3 | 1/5 |
| No hándicap | De 5 a 7 | 2 | 1/4 |
| Precio | Incremento |
| --- | --- |
| 1,01 2 | 0,01 |
| 2 3 | 0,02 |
| 3 4 | 0,05 |
| 4 6 | 0,1 |
| 6 10 | 0,2 |
| 10 20 | 0,5 |
| 20 30 | 1 |
| 30 50 | 2 |
| 50 100 | 5 |
| 100 1000 | 10 |
| Precio | Incremento |
| --- | --- |
| 1,01 1000 | 0,01 |
| Nombre de moneda | Símbolo | Tamaño de apuesta mín. | Tamaño de depósito mín. | Riesgo de BSP mín. |
| --- | --- | --- | --- | --- |
| Libras esterlinas | GBP | 2 | 10 | 10 |
| Euro | EUR | 2 | 15 | 20 |
| Dólar estadounidense | USD | 4 | 15 | 20 |
| Dólar de Hong Kong | HKD | 25 | 150 | 125 |
| Dólar australiano | AUD | 5 | 30 | 30 |
| Dólar canadiense | CAD | 6 | 25 | 30 |
| Coronas Danesas | DKK | 30 | 150 | 150 |
| Coronas noruegas | NOK | 30 | 150 | 150 |
| Corona sueca | SEK | 30 | 150 | 150 |
| Dólar de Singapur | SGD | 6 | 30 | 30 |
| cancelOrders | cancelOrders | cancelOrders | cancelOrders | cancelOrders | cancelOrders | cancelOrders | cancelOrders | cancelOrders |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | CancelExecutionReport cancelOrders (StringmarketId,List< CancelInstruction >instructions,Stringcust omerRef) muestra APINGException

Cancelar todas las apuestas O cancelar todas las apuestas en un mercado O cancelar total o parcialmente pedidos particulares en un mercado. Solo los pedidos LÍMITE se pueden cancelar total o parcialmente una vez hechos. | CancelExecutionReport cancelOrders (StringmarketId,List< CancelInstruction >instructions,Stringcust omerRef) muestra APINGException

Cancelar todas las apuestas O cancelar todas las apuestas en un mercado O cancelar total o parcialmente pedidos particulares en un mercado. Solo los pedidos LÍMITE se pueden cancelar total o parcialmente una vez hechos. | CancelExecutionReport cancelOrders (StringmarketId,List< CancelInstruction >instructions,Stringcust omerRef) muestra APINGException

Cancelar todas las apuestas O cancelar todas las apuestas en un mercado O cancelar total o parcialmente pedidos particulares en un mercado. Solo los pedidos LÍMITE se pueden cancelar total o parcialmente una vez hechos. | CancelExecutionReport cancelOrders (StringmarketId,List< CancelInstruction >instructions,Stringcust omerRef) muestra APINGException

Cancelar todas las apuestas O cancelar todas las apuestas en un mercado O cancelar total o parcialmente pedidos particulares en un mercado. Solo los pedidos LÍMITE se pueden cancelar total o parcialmente una vez hechos. | CancelExecutionReport cancelOrders (StringmarketId,List< CancelInstruction >instructions,Stringcust omerRef) muestra APINGException

Cancelar todas las apuestas O cancelar todas las apuestas en un mercado O cancelar total o parcialmente pedidos particulares en un mercado. Solo los pedidos LÍMITE se pueden cancelar total o parcialmente una vez hechos. | CancelExecutionReport cancelOrders (StringmarketId,List< CancelInstruction >instructions,Stringcust omerRef) muestra APINGException

Cancelar todas las apuestas O cancelar todas las apuestas en un mercado O cancelar total o parcialmente pedidos particulares en un mercado. Solo los pedidos LÍMITE se pueden cancelar total o parcialmente una vez hechos. | CancelExecutionReport cancelOrders (StringmarketId,List< CancelInstruction >instructions,Stringcust omerRef) muestra APINGException

Cancelar todas las apuestas O cancelar todas las apuestas en un mercado O cancelar total o parcialmente pedidos particulares en un mercado. Solo los pedidos LÍMITE se pueden cancelar total o parcialmente una vez hechos. |  |
|  | Nombre de parámetro | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción | Descripción |  |
|  | marketId | marketId | Cadena | Cadena |  | Si no se proporcionan marketId y betId, 
se cancelan todas las apuestas | Si no se proporcionan marketId y betId, 
se cancelan todas las apuestas |  |
|  | instructions | instructions | Lista< Cancel Instruction > | Lista< Cancel Instruction > |  | Todas las instrucciones deben estar en el mismo mercado. Si no se suministran todas las apuestas en el mercado (en el caso de que se pase el ID de mercado), estas se cancelan totalmente. El límite de instrucciones de cancelación por solicitud es 60 | Todas las instrucciones deben estar en el mismo mercado. Si no se suministran todas las apuestas en el mercado (en el caso de que se pase el ID de mercado), estas se cancelan totalmente. El límite de instrucciones de cancelación por solicitud es 60 |  |
|  | customerRef | customerRef | Cadena | Cadena |  | Parámetro opcional que permite al cliente pasar una cadena única (hasta 32 caracteres) que se utiliza para desduplicar nuevos envíos confundidos. | Parámetro opcional que permite al cliente pasar una cadena única (hasta 32 caracteres) que se utiliza para desduplicar nuevos envíos confundidos. |  |
|  |  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Tipo de retorno | Descripción | Descripción | Descripción |  |  |
|  | CancelExecutionReport | CancelExecutionReport | CancelExecutionReport |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| replaceOrders | replaceOrders | replaceOrders | replaceOrders | replaceOrders | replaceOrders | replaceOrders | replaceOrders |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  | ReplaceExecutionReport replaceOrders (StringmarketId , List< ReplaceInstruction >instructions , StringcustomerRef, MarketVersion marketVersion, boolean async ) muestra APINGException

Esta operación es lógicamente una cancelación por volumen seguida de una colocación por volumen. En primer lugar, se realiza la cancelación y, luego, se hacen los nuevos pedidos. Los nuevos pedidos se colocarán automáticamente, ya que o se colocar todos o ninguno. En caso de que los nuevos pedidos no se puedan colocar, 
las cancelaciones no se revertirán. Vea ReplaceInstruction. | ReplaceExecutionReport replaceOrders (StringmarketId , List< ReplaceInstruction >instructions , StringcustomerRef, MarketVersion marketVersion, boolean async ) muestra APINGException

Esta operación es lógicamente una cancelación por volumen seguida de una colocación por volumen. En primer lugar, se realiza la cancelación y, luego, se hacen los nuevos pedidos. Los nuevos pedidos se colocarán automáticamente, ya que o se colocar todos o ninguno. En caso de que los nuevos pedidos no se puedan colocar, 
las cancelaciones no se revertirán. Vea ReplaceInstruction. | ReplaceExecutionReport replaceOrders (StringmarketId , List< ReplaceInstruction >instructions , StringcustomerRef, MarketVersion marketVersion, boolean async ) muestra APINGException

Esta operación es lógicamente una cancelación por volumen seguida de una colocación por volumen. En primer lugar, se realiza la cancelación y, luego, se hacen los nuevos pedidos. Los nuevos pedidos se colocarán automáticamente, ya que o se colocar todos o ninguno. En caso de que los nuevos pedidos no se puedan colocar, 
las cancelaciones no se revertirán. Vea ReplaceInstruction. | ReplaceExecutionReport replaceOrders (StringmarketId , List< ReplaceInstruction >instructions , StringcustomerRef, MarketVersion marketVersion, boolean async ) muestra APINGException

Esta operación es lógicamente una cancelación por volumen seguida de una colocación por volumen. En primer lugar, se realiza la cancelación y, luego, se hacen los nuevos pedidos. Los nuevos pedidos se colocarán automáticamente, ya que o se colocar todos o ninguno. En caso de que los nuevos pedidos no se puedan colocar, 
las cancelaciones no se revertirán. Vea ReplaceInstruction. | ReplaceExecutionReport replaceOrders (StringmarketId , List< ReplaceInstruction >instructions , StringcustomerRef, MarketVersion marketVersion, boolean async ) muestra APINGException

Esta operación es lógicamente una cancelación por volumen seguida de una colocación por volumen. En primer lugar, se realiza la cancelación y, luego, se hacen los nuevos pedidos. Los nuevos pedidos se colocarán automáticamente, ya que o se colocar todos o ninguno. En caso de que los nuevos pedidos no se puedan colocar, 
las cancelaciones no se revertirán. Vea ReplaceInstruction. | ReplaceExecutionReport replaceOrders (StringmarketId , List< ReplaceInstruction >instructions , StringcustomerRef, MarketVersion marketVersion, boolean async ) muestra APINGException

Esta operación es lógicamente una cancelación por volumen seguida de una colocación por volumen. En primer lugar, se realiza la cancelación y, luego, se hacen los nuevos pedidos. Los nuevos pedidos se colocarán automáticamente, ya que o se colocar todos o ninguno. En caso de que los nuevos pedidos no se puedan colocar, 
las cancelaciones no se revertirán. Vea ReplaceInstruction. |  |
|  | Nombre de parámetro | Tipo | Tipo | Tipo | Obligatorio | Descripción |  |
|  | marketId | Cadena | Cadena | Cadena |  | El ID del mercado en el que se harán estas órdenes |  |
|  | instructions | Lista< ReplaceInstruction > | Lista< ReplaceInstruction > | Lista< ReplaceInstruction > |  | El número de instrucciones de nuevas colocaciones. El límite de instrucciones de nuevas colocaciones por solicitud es 60 |  |
|  | customerRef | Cadena | Cadena | Cadena |  | Parámetro opcional que permite al cliente pasar una cadena única (hasta 32 caracteres) que se utiliza para desduplicar nuevos envíos confundidos. |  |
|  | marketVersion | MarketVersion | MarketVersion | MarketVersion |  | Parámetro opcional que permite al cliente especificar en qué versión del mercado se deben hacer los pedidos. Si la versión actual del mercado es mayor que la que se envió en un pedido, la apuesta caducará. |  |
|  | async | boolean | boolean | boolean |  | Un marcador opcional (ningún ajuste equivale a falso) que especifica si los pedidos deben sustituirse de forma asincrónica.
Los pedidos se pueden rastrear a través de la API de secuencia de Exchange o API-NG al proporcionar una customerOrderRef para cada pedido de nueva colocación.
No disponible para apuestas MOC o LOC. |  |
|  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | ReplaceExecutionReport | ReplaceExecutionReport | ReplaceExecutionReport |  |  |  |  |
|  |  |  |  |  |  |  |  |
|  | Muestra | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| updateOrders | updateOrders | updateOrders | updateOrders | updateOrders | updateOrders | updateOrders | updateOrders |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  | UpdateExecutionReport updateOrders (StringmarketId , List< UpdateInstruction >instructions ,StringcustomerRef ) muestra APINGException

Actualizar los campos que cambien sin exposición | UpdateExecutionReport updateOrders (StringmarketId , List< UpdateInstruction >instructions ,StringcustomerRef ) muestra APINGException

Actualizar los campos que cambien sin exposición | UpdateExecutionReport updateOrders (StringmarketId , List< UpdateInstruction >instructions ,StringcustomerRef ) muestra APINGException

Actualizar los campos que cambien sin exposición | UpdateExecutionReport updateOrders (StringmarketId , List< UpdateInstruction >instructions ,StringcustomerRef ) muestra APINGException

Actualizar los campos que cambien sin exposición | UpdateExecutionReport updateOrders (StringmarketId , List< UpdateInstruction >instructions ,StringcustomerRef ) muestra APINGException

Actualizar los campos que cambien sin exposición | UpdateExecutionReport updateOrders (StringmarketId , List< UpdateInstruction >instructions ,StringcustomerRef ) muestra APINGException

Actualizar los campos que cambien sin exposición |  |
|  | Nombre de parámetro | Tipo | Tipo | Tipo | Obligatorio | Descripción |  |
|  | marketId | Cadena | Cadena | Cadena |  | El ID del mercado en el que se harán estas órdenes |  |
|  | instructions | Lista< UpdateInstruction > | Lista< UpdateInstruction > | Lista< UpdateInstruction > |  | El número de instrucciones de actualización. El límite de instrucciones de actualización por solicitud es 60 |  |
|  | customerRef | Cadena | Cadena | Cadena |  | Parámetro opcional que permite al cliente pasar una cadena única (hasta 32 caracteres) que se utiliza para desduplicar nuevos envíos confundidos. |  |
|  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | UpdateExecutionReport | UpdateExecutionReport | UpdateExecutionReport |  |  |  |  |
|  |  |  |  |  |  |  |  |
|  | Muestra | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| APINGException | APINGException | APINGException | APINGException | APINGException | APINGException | APINGException |
| --- | --- | --- | --- | --- | --- | --- |
|  | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación |  |
|  |  |  |  |  |  |  |
|  | Otros parámetros | Tipo | Obligatorio | Descripción | Valores |  |
|  | Otros parámetros | Tipo | Obligatorio | Descripción | Valores |  |
|  | errorDetails | Cadena |  | el seguimiento de la apuesta de error | “el ID de mercado no es válido”

“la región debe usar nombres válidos de ISO 639”

“la moneda debe utilizar el nombre de código de moneda válido de ISO2"

“el código de país debe utilizar el nombre de código de país válido de ISO2"
 “la consulta de texto tiene contenido no válido"

“el idioma debe utilizar un nombre de idioma válido de ISO" |  |
|  | requestUUID | Cadena |  |  |  |  |
|  |  |  |  |  |  |  |
| Código de error | Descripción |
| --- | --- |
| -32700 | El servidor recibió un JSON no válido. Se ha producido un error en el servidor al analizar el texto de JSON. |
| -32601 | No se ha encontrado el método. |
| -32602 | Problema al analizar los parámetros, o un parámetro obligatorio no fue encontrado. |
| -32603 | Error de JSON-RPC interno |
| MarketProjection | MarketProjection | MarketProjection | MarketProjection |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | COMPETITION | Si no se selecciona, entonces la competencia no se devolverá con marketCatalogue |  |
|  | EVENT | Si no se selecciona, el evento no se devolverá con marketCatalogue |  |
|  | EVENT_TYPE | Si no se selecciona, el eventType no se devolverá con marketCatalogue |  |
|  | MARKET_START_TIME | Si no se selecciona, la hora de inicio no se devolverá con marketCatalogue |  |
|  | MARKET_DESCRIPTION | Si no se selecciona, la descripción no se devolverá con marketCatalogue |  |
|  | RUNNER_DESCRIPTION | Si no se seleccionan, los corredores no se devolverán con marketCatalogue |  |
|  | RUNNER_METADATA | Si no se seleccionan, los metadatos de los corredores no se devolverán con marketCatalogue Si se selecciona, RUNNER_DESCRIPTION se devolverá también independientemente de si está incluido como una proyección de mercado. |  |
|  |  |  |  |
| PriceData | PriceData | PriceData | PriceData |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | SP_AVAILABLE | Cantidad disponible para la subasta de BSP. |  |
|  | SP_TRADED | Cantidad negociada para la subasta de BSP. |  |
|  | EX_BEST_OFFERS | Solo los mejores precios disponibles para cada corredor, a la profundidad de precio solicitada. |  |
|  | EX_ALL_OFFERS | EX_ALL_OFFERS supera EX_BEST_OFFERS si están presentes ambos ajustes |  |
|  | EX_TRADED | Cantidad negociada en el intercambio |  |
|  |  |  |  |
| MatchProjection | MatchProjection | MatchProjection | MatchProjection |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | NO_ROLLUP | Sin acumulación, devuelve fragmentos sin procesar |  |
|  | ROLLED_UP_BY_PRICE | Cantidades acumuladas que coinciden con distintos precios coincidentes por lado. |  |
|  | ROLLED_UP_BY_AVG_PRICE | Cantidades acumuladas que coinciden con precios promedio coincidentes por lado. |  |
|  |  |  |  |
| OrderProjection | OrderProjection | OrderProjection | OrderProjection |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | ALL | Pedidos EXECUTABLE y EXECUTION_COMPLETE |  |
|  | EXECUTABLE | Un pedido que tiene una parte restante sin coincidencia |  |
|  | EXECUTION_COMPLETE | Un pedido que no tiene ninguna parte restante sin coincidencia |  |
|  |  |  |  |
| MarketStatus | MarketStatus | MarketStatus | MarketStatus | MarketStatus |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |
|  | Valor | Descripción |  |  |
|  | INACTIVE | Se ha creado el mercado, pero todavía no está disponible. |  |  |
|  | OPEN | El mercado está abierto para las apuestas. |  |  |
|  | SUSPENDED | El mercado está suspendido y no disponible para apostar. |  |  |
|  | CLOSED | El mercado se ha asentado y ya no está disponible para apostar. |  |  |
|  |  |  |  |  |
| RunnerStatus | RunnerStatus | RunnerStatus | RunnerStatus | RunnerStatus |
|  |  |  |  |  |
|  | Valor | Descripción | Descripción |  |
|  | ACTIVE | ACTIVE | ACTIVE |  |
|  | WINNER | WINNER | WINNER |  |
|  | LOSER | LOSER | LOSER |  |
|  | PLACED | Se colocó el corredor, se aplica a los marketTypes EACH_WAY solamente. | Se colocó el corredor, se aplica a los marketTypes EACH_WAY solamente. |  |
|  | REMOVED_VACANT | REMOVED_VACANT se aplica solo a los galgos. Los mercados de galgos siempre devuelven un número fijo de corredores (bancos). Si un perro ha sido eliminado, el banco se muestra como vacante. | REMOVED_VACANT se aplica solo a los galgos. Los mercados de galgos siempre devuelven un número fijo de corredores (bancos). Si un perro ha sido eliminado, el banco se muestra como vacante. |  |
|  | REMOVED | REMOVED | REMOVED |  |
|  | HIDDEN | La selección está oculta en el mercado. Esto ocurre en los mercados de carreras de caballos donde los corredores se ocultan cuando no tienen una entrada oficial tras una fase de entrada. Esto podría ser porque el caballo nunca entró o porque se ha quitado de una carrera en una etapa de declaración. Todos los precios de las apuestas del cliente que coincidan se fijan en 1,0, incluso si existen etapas complementarias posteriores. Si parece probable que un corredor específico pueda realmente ser complementado en la carrera, este corredor se deberá reinstalar con todas las apuestas coincidentes del cliente regresadas al precio original. | La selección está oculta en el mercado. Esto ocurre en los mercados de carreras de caballos donde los corredores se ocultan cuando no tienen una entrada oficial tras una fase de entrada. Esto podría ser porque el caballo nunca entró o porque se ha quitado de una carrera en una etapa de declaración. Todos los precios de las apuestas del cliente que coincidan se fijan en 1,0, incluso si existen etapas complementarias posteriores. Si parece probable que un corredor específico pueda realmente ser complementado en la carrera, este corredor se deberá reinstalar con todas las apuestas coincidentes del cliente regresadas al precio original. |  |
|  |  |  |  |  |
| TimeGranularity | TimeGranularity | TimeGranularity | TimeGranularity |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | DAYS |  |  |
|  | HOURS |  |  |
|  | MINUTES |  |  |
|  |  |  |  |
| Lado | Lado | Lado | Lado | Lado | Lado |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
|  |  | Valor | Descripción | Descripción |  |
|  |  | BACK | Para estar a favor de un equipo, caballo o resultado debe apostar por la selección para que gane. Para mercados de LÍNEA, una apuesta a favor se refiere a una línea de VENTA. Una línea de VENTA se gana si el resultado es INFERIOR A la línea tomada (precio). | Para estar a favor de un equipo, caballo o resultado debe apostar por la selección para que gane. Para mercados de LÍNEA, una apuesta a favor se refiere a una línea de VENTA. Una línea de VENTA se gana si el resultado es INFERIOR A la línea tomada (precio). |  |
|  |  | LAY | Para estar en contra de un equipo, caballo o resultado debe apostar por la selección para que pierda. Para mercados de LÍNEA, una apuesta en contra se refiere a una línea de COMPRA. Una línea de COMPRA se gana si el resultado es SUPERIOR A la línea tomada (precio). | Para estar en contra de un equipo, caballo o resultado debe apostar por la selección para que pierda. Para mercados de LÍNEA, una apuesta en contra se refiere a una línea de COMPRA. Una línea de COMPRA se gana si el resultado es SUPERIOR A la línea tomada (precio). |  |
|  |  |  |  |  |  |
| OrderStatus | OrderStatus | OrderStatus | OrderStatus | OrderStatus | OrderStatus |
|  |  |  |  |  |  |
|  | Valor | Valor | Valor | Descripción |  |
|  | PENDING | PENDING | PENDING | Un pedido asíncrono aún no se ha procesado. Una vez que el intercambio haya procesado la apuesta (incluida la espera por cualquier demora en juego), el resultado será informado y estará disponible en la API de secuencia de Exchange y la API NG.
No es un criterio de búsqueda válido en MarketFilter |  |
|  | EXECUTION_COMPLETE | EXECUTION_COMPLETE | EXECUTION_COMPLETE | Un pedido que no tiene ninguna parte restante sin coincidencia. |  |
|  | EXECUTABLE | EXECUTABLE | EXECUTABLE | Un pedido que tiene una parte restante sin coincidencia. |  |
|  | EXPIRED | EXPIRED | EXPIRED | El pedido ya no está disponible para su ejecución debido a su restricción de tiempo en vigor.
En el caso de los pedidos FILL_OR_KILL, esto significa que el pedido se ha eliminado porque no pudo completar sus especificaciones.
No es un criterio de búsqueda válido en MarketFilter |  |
|  |  |  |  |  |  |
| OrderBy | OrderBy | OrderBy | OrderBy |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | BY_BET | @Uso suplantado BY_PLACE_TIME en su lugar. Ordenar por tiempo de realización, luego por ID de apuesta. |  |
|  | BY_MARKET | Ordenar por ID de mercado, luego por ID de apuesta. |  |
|  | BY_MATCH_TIME | Ordenar por hora del último fragmento coincidente (si hubiera), luego el tiempo de realización, después ID de apuesta. Se filtran los pedidos que no tienen fecha coincidente. El filtro dateRange (si se especifica) se aplica a la fecha que coincide. |  |
|  | BY_PLACE_TIME | Ordenar por tiempo de realización, luego por ID de apuesta. Se trata de un alias de ser suplantado BY_BET. El filtro dateRange (si se especifica) se aplica a la fecha de realización. |  |
|  | BY_SETTLED_TIME | Ordenar por tiempo del último fragmento asentado (si hay alguno debido al asentamiento del mercado parcial), luego por hora del último partido, después por ID de apuesta. Filtra los pedidos que no se han asentado. El filtro dateRange (si se especifica) se aplica a la fecha de asentamiento. |  |
|  | BY_VOID_TIME | Ordenar por tiempo del último fragmento anulado (si hay alguno), luego por hora del último partido, después por hora de colocación y por ID de apuesta. Filtra los pedidos que no se han anulado. El filtro dateRange (si se especifica) se aplica a la fecha de anulación. |  |
|  |  |  |  |
| SortDir | SortDir | SortDir | SortDir |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | EARLIEST_TO_LATEST | Ordena desde el valor la más antiguo al más reciente, por ejemplo, el betid más bajo está en primer lugar en los resultados. |  |
|  | LATEST_TO_EARLIEST | Ordena desde el valor la más reciente al más antiguo, por ejemplo, el betid más alto está en primer lugar en los resultados. |  |
|  |  |  |  |
| OrderType | OrderType | OrderType | OrderType |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | LIMIT | Un orden de límite de intercambio normal para su ejecución inmediata |  |
|  | LIMIT_ON_CLOSE | Orden de límite para la subasta (SP) |  |
|  | MARKET_ON_CLOSE | Orden de mercado para la subasta (SP) |  |
|  |  |  |  |
| MarketSort | MarketSort | MarketSort | MarketSort |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | MINIMUM_TRADED | El volumen mínimo negociado |  |
|  | MAXIMUM_TRADED | El volumen máximo negociado |  |
|  | MINIMUM_AVAILABLE | Valor promedio mínimo para hacer coincidir |  |
|  | MAXIMUM_AVAILABLE | Valor promedio máximo para hacer coincidir |  |
|  | FIRST_TO_START | Los mercados más cercanos según su hora de inicio prevista |  |
|  | LAST_TO_START | Los mercados más distantes según su hora de inicio prevista |  |
|  |  |  |  |
| MarketBettingType | MarketBettingType | MarketBettingType | MarketBettingType |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | ODDS | Mercado de probabilidades. Cualquier mercado que no encaja en ninguna de las siguientes categorías. |  |
|  | LINE | Mercado de línea. Los mercados de línea operan en probabilidades de dinero parejo de 2,0. Sin embargo, el precio de estos mercados se refiere a las ubicaciones de línea disponibles según lo definido por el rango mínimo - máximo de los mercados y los pasos de intervalo. Los clientes compran una línea (apuesta en contra que gana si el resultado es superior a la línea tomada [precio]) o venden una línea (apuesta a favor que gana si el resultado es inferior a la línea tomada [precio]). Si el resultado asentado equivale a la línea tomada, se devuelve la apuesta. |  |
|  | RANGE | Mercado de rango. Ahora suplantado |  |
|  | ASIAN_HANDICAP_DOUBLE_LINE | Mercado de hándicap asiático. Un mercado de hándicap asiático tradicional. Se puede identificar por marketType ASIAN_HANDICAP |  |
|  | ASIAN_HANDICAP_SINGLE_LINE | Mercado de línea única asiático. Un mercado en el que puede haber 0 o varios ganadores. P. ej., marketType TOTAL_GOALS |  |
|  | FIXED_ODDS | Mercado de probabilidades del Sportsbook. Este tipo está suplantado y se eliminará en futuras versiones, cuando los mercados de Sportsbook se representen como mercados de ODDS, pero con un tipo diferente de producto. |  |
|  |  |  |  |
| ExecutionReportStatus | ExecutionReportStatus | ExecutionReportStatus | ExecutionReportStatus |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | SUCCESS | El pedido se ha procesado correctamente |  |
|  | FAILURE | Error en el pedido. |  |
|  | PROCESSED_WITH_ERRORS | El pedido se ha aceptado, pero al menos una acción (posiblemente todas) ha generado errores. Este error solo se produce por operaciones de replaceOr ders, cancelOrders y updateOrders. La operación placeOrd ers no devolverá el estado PROCESSED_WITH_ERRORS, ya que es una operación atómica. |  |
|  | TIMEOUT | El tiempo de espera del pedido caducó. |  |
|  |  |  |  |
| ExecutionReportErrorCode | ExecutionReportErrorCode | ExecutionReportErrorCode | ExecutionReportErrorCode |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | ERROR_IN_MATCHER | La coincidencia no es correcta |  |
|  | PROCESSED_WITH_ERRORS | Se ha aceptado el pedido, pero al menos una acción (posiblemente todas) ha generado errores |  |
|  | BET_ACTION_ERROR | Hay un error con una acción que ha hecho que se rechace todo el pedido. Verifique en instructionReports errorCode el motivo del rechazo del pedido. |  |
|  | INVALID_ACCOUNT_STATE | Pedido rechazado debido al estado de la cuenta (suspendida, inactiva, tarjetas duplicadas) |  |
|  | INVALID_WALLET_STATUS | Pedido rechazado debido al estado de la billetera de la cuenta |  |
|  | INSUFFICIENT_FUNDS | La cuenta ha excedido su límite de exposición o el límite de disponible para apuesta |  |
|  | LOSS_LIMIT_EXCEEDED | La cuenta ha superado el límite de pérdida autoimpuesto |  |
|  | MARKET_SUSPENDED | El mercado está suspendido |  |
|  | MARKET_NOT_OPEN_FOR_BETTING | El mercado no está abierto para apuestas. Todavía no está activo, suspendido o cerrado pendiente de asentamiento. |  |
|  | DUPLICATE_TRANSACTION | Datos de referencia de clientes duplicados presentados. Tenga en cuenta lo siguiente: Existe una ventana de tiempo asociada con la desduplicación de presentaciones duplicadas que es de 60 segundos |  |
|  | INVALID_ORDER | La coincidencia no puede aceptar el pedido debido a la combinación de acciones. Por ejemplo, las apuestas que se editan no están en el mismo mercado, o el pedido incluye la edición y realización |  |
|  | INVALID_MARKET_ID | No existe el mercado |  |
|  | PERMISSION_DENIED | Las reglas de negocio no permiten hacer el pedido. Está intentando realizar el pedido utilizando una clave de aplicación retardada o de una jurisdicción restringida (p. ej., EE. UU.) |  |
|  | DUPLICATE_BETIDS | Se encontraron ID de apuestas duplicados |  |
|  | NO_ACTION_REQUIRED | El pedido no se ha pasado a la coincidencia, ya que el sistema detectó que no habrá ningún cambio de estado |  |
|  | SERVICE_UNAVAILABLE | El servicio solicitado no está disponible |  |
|  | REJECTED_BY_REGULATOR | El regulador rechazó el pedido. En el Exchange italiano este error ocurrirá si más de 50 apuestas se envían en una sola solicitud de placeOrders. |  |
|  | NO_CHASING | Un código de error específico que se relaciona únicamente con los mercados de Exchange (Intercambio) españoles, que indica que la apuesta contraviene la normativa española relacionada con la búsqueda de pérdidas. |  |
| --- | --- | --- | --- |
|  | REGULATOR_IS_NOT_AVAILABLE | El servicio del regulador subyacente no está disponible. |  |
|  | TOO_MANY_INSTRUCTIONS | La cantidad de pedidos superaba el importe máximo permitido para ser ejecutado |  |
|  | INVALID_MARKET_VERSION | La versión de mercado proporcionada no es válida. La longitud máxima permitida para la versión del mercado es 12. |  |
|  |  |  |  |
| PersistenceType | PersistenceType | PersistenceType | PersistenceType | PersistenceType | PersistenceType |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
|  | Valor | Valor | Valor | Descripción |  |
|  | LAPSE | LAPSE | LAPSE | Caducidad del pedido cuando el mercado se cambia en juego |  |
|  | PERSIST | PERSIST | PERSIST | Persistencia del pedido en juego. La apuesta se colocará automáticamente en el mercado en juego en el inicio del evento. |  |
|  | MARKET_ON_CLOSE | MARKET_ON_CLOSE | MARKET_ON_CLOSE | Coloca el pedido en la subasta (SP) en el cambio 
en juego |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
| InstructionReportStatus | InstructionReportStatus | InstructionReportStatus | InstructionReportStatus | InstructionReportStatus | InstructionReportStatus |
|  |  |  |  |  |  |
|  | Valor | Descripción |  |  |  |
|  | SUCCESS |  |  |  |  |
|  | FAILURE |  |  |  |  |
|  | TIMEOUT |  |  |  |  |
|  |  |  |  |  |  |
| InstructionReportErrorCode | InstructionReportErrorCode | InstructionReportErrorCode | InstructionReportErrorCode |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | INVALID_BET_SIZE | El tamaño de apuesta no es válido para su moneda o su regulador |  |
|  | INVALID_RUNNER | El corredor no existe, incluye bancos vacantes en las carreras de galgos |  |
|  | BET_TAKEN_OR_LAPSED | La apuesta no se puede cancelar o
 modificar, ya que se ha tomado o se ha cancelado/caducó. Incluye los intentos de cancelar/modificar el mercado en las apuestas BSP cerradas y el límite de cancelación en las apuestas de BSP cerradas. El error puede aparecer en la solicitud de placeOrders si, por ejemplo, una apuesta se hace cuando ocurre un evento de administración de mercado (es decir, el mercado se cambió en juego) |  |
|  | BET_IN_PROGRESS | No se ha recibido ningún resultado de la coincidencia en un tiempo de espera configurado para el sistema |  |
|  | RUNNER_REMOVED | El corredor ha sido eliminado del evento |  |
|  | MARKET_NOT_OPEN_FOR_BETTING | Intenta modificar una apuesta en un mercado que se ha cerrado. |  |
|  | LOSS_LIMIT_EXCEEDED | La acción ha hecho que la cuenta exceda el límite de pérdida de autoimpuesto |  |
|  | MARKET_NOT_OPEN_FOR_BSP_BETTING | El mercado ahora está cerrado para las apuestas de bsp. Se cambió en juego o se ha reconciliado |  |
|  | INVALID_PRICE_EDIT | Intente modificar hacia abajo el precio de un límite de bsp en una apuesta en contra cerrada, o modificar hacia arriba el precio de un límite en una apuesta a favor cerrada |  |
|  | INVALID_ODDS | Probabilidades que no se encuentran en la escalera de precios, ya sea edición o colocación |  |
|  | INSUFFICIENT_FUNDS | Fondos insuficientes disponibles para cubrir la acción de la apuesta. Se superaría el límite de exposición o el límite de disponible para apostar |  |
|  | INVALID_PERSISTENCE_TYPE | Tipo de persistencia no válida para este mercado, por ejemplo, KEEP para un mercado no en juego. |  |
|  | ERROR_IN_MATCHER | Un problema con la coincidencia impidió que esta acción se complete correctamente |  |
|  | INVALID_BACK_LAY_COMBINATION | El pedido contiene una apuesta a favor y una en contra para el mismo corredor a precios que se superponen. Esto garantizaría una autocoincidencia. Esto también se aplica al límite de BSP en las apuestas cerradas |  |
|  | ERROR_IN_ORDER | La acción ha fallado porque el pedido principal falló |  |
|  | INVALID_BID_TYPE | El tipo de oferta es obligatorio |  |
|  | INVALID_BET_ID | No se encontró la apuesta para el ID suministrado |  |
|  | CANCELLED_NOT_PLACED | Apuesta cancelada, pero la apuesta sustituta no se realizó |  |
|  | RELATED_ACTION_FAILED | La acción ha fallado debido al error de una acción de la que depende esta acción |  |
|  | NO_ACTION_REQUIRED | La acción no produce ningún cambio de estado. Por ejemplo, cambiar una persistencia a su valor actual |  |
|  | TIME_IN_FORCE_CONFLICT | Solo puede especificar un tiempo en vigor, ya sea en la solicitud de la colocación O en las instrucciones de pedido de límite individual (no en ambas),
ya que los comportamientos implícitos son incompatibles. |  |
|  | UNEXPECTED_PERSISTENCE_TYPE | Se ha especificado un tipo de persistencia para el pedido de FILL_OR_KILL, lo cual es absurdo porque ninguna parte que no coincida
puede permanecer una vez realizado el pedido. |  |
|  | INVALID_ORDER_TYPE | Ha especificado un tiempo en vigor de FILL_OR_KILL, pero ha incluido un tipo de pedido sin límite. |  |
|  | UNEXPECTED_MIN_FILL_SIZE | Ha especificado un minFillSize en un pedido límite, donde el tiempo en vigor del pedido límite no es FILL_OR_KILL.
El uso de minFillSize no es compatible cuando el tiempo en vigor de la solicitud (en contraposición a un pedido) es FILL_OR_KILL. |  |
|  | INVALID_CUSTOMER_ORDER_REF | La referencia del pedido del cliente suministrada es demasiado larga. |  |
|  | INVALID_MIN_FILL_SIZE | El minFillSize debe ser mayor que cero y menor o igual que el tamaño del pedido.
El minFillSize no puede ser menor que el tamaño mínimo de apuesta para su moneda |  |
|  |  |  |  |
| RollupModel | RollupModel | RollupModel | RollupModel |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | STAKE | Los volúmenes se acumularán hasta el valor mínimo que es >= rollupLimit. |  |
|  | PAYOUT | Los volúmenes se acumularán hasta el valor mínimo donde el pago (precio * volumen) es >= rollupLimit. En un mercado de LÍNEA, los volúmenes se acumulan donde el pago (2,0 * volumen) es >= rollupLimit |  |
|  | MANAGED_LIABILITY | Los volúmenes se acumularán hasta el valor mínimo que es >= rollupLimit, hasta el umbral del precio de una apuesta en contra. Luego, los volúmenes se acumularán en el valor mínimo de manera tal que el riesgo sea >= un riesgo mínimo. Todavía no se admite. |  |
|  | NONE | No se aplicará ninguna acumulación. Sin embargo, los volúmenes se filtrarán por apuesta mínima específica 
de moneda, a menos que se anule específicamente para el canal. |  |
|  |  |  |  |
| GroupBy | GroupBy | GroupBy | GroupBy |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | EVENT_TYPE | Una acumulación de P&L asentado, comisión pagada y número de pedidos de apuesta, en un determinado tipo de evento |  |
|  | EVENT | Una acumulación de P&L asentado, comisión pagada y número de pedidos de apuesta, en un determinado evento |  |
|  | MARKET | Una acumulación de P&L asentado, comisión pagada y número de pedidos de apuesta, en un determinado mercado |  |
|  | SIDE | Una acumulación promedio de P&L asentado, y el número de apuestas, en el lado especificado de una selección determinada dentro de un mercado específico, que está asentado o anulado |  |
|  | BET | El P&L, la comisión pagada, información lateral y reglamentaria, etc., acerca de cada pedido de apuesta individual |  |
|  |  |  |  |
| BetStatus | BetStatus | BetStatus | BetStatus |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | SETTLED | Una apuesta coincidente que se asentó normalmente |  |
|  | VOIDED | Una apuesta coincidente que posteriormente fue anulada por Betfair, antes, durante o después del asentamiento |  |
|  | LAPSED | Apuesta sin coincidencia que fue cancelada por Betfair (por ejemplo, en el cambio en juego). |  |
|  | CANCELLED | Apuesta sin coincidencia que fue cancelada por una acción explícita del cliente. |  |
|  |  |  |  |
| marketType: datos heredados | marketType: datos heredados | marketType: datos heredados | marketType: datos heredados |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | H | Hándicap asiático |  |
|  | M | Mercado de línea |  |
|  | MP | Mercado de posibilidades |  |
|  | MR | Mercado de rangos |  |
|  | NOT_APPLICABLE | El mercado no tiene un marketType aplicable. |  |
|  |  |  |  |
| TimeInForce | TimeInForce | TimeInForce | TimeInForce |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | FILL_OR_KILL | Ejecuta la transacción de manera inmediata y completa (de forma llena hasta el tamaño o entre minFillSize y el tamaño) o no la ejecuta para nada (cancelado).

Para mercados de LÍNEA, la funcionalidad de precio promedio ponderado por volumen (VWAP) está deshabilitada |  |
|  |  |  |  |
| BetTargetType | BetTargetType | BetTargetType | BetTargetType |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | BACKERS_PROFIT | El pago solicitado menos el tamaño calculado en que se realiza este LimitOrder. Las apuestas de BetTargetType no son válidas para mercados de LÍNEA |  |
|  | PAYOUT | El pago total solicitado en un LimitOrder |  |
|  |  |  |  |
| MarketFilter | MarketFilter | MarketFilter | MarketFilter | MarketFilter | MarketFilter |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | textQuery | Cadena |  | Restringir los mercados por cualquier texto asociado con el mercado, como el nombre, el evento, la competencia, etc. Puede incluir un carácter comodín (*) siempre que no sea el primer carácter. |  |
|  | exchangeIds | Establecer<String> |  | DEPRECATED |  |
|  | eventTypeIds | Establecer<String> |  | Restringe los mercados por tipo de evento asociado con el mercado. (Es decir, fútbol, hockey, etc.) |  |
|  | eventIds | Establecer<String> |  | Restringe los mercados por el ID de evento asociado con el mercado. |  |
|  | competitionIds | Establecer<String> |  | Restringe los mercados por la competencia asociada con el mercado. |  |
|  | marketIds | Establecer<String> |  | Restringe los mercados por el ID de mercado asociado con el mercado. |  |
|  | venues | Establecer<String> |  | Restringe los mercados por el lugar asociado con el mercado. Actualmente, solo los mercados de carreras de caballos tienen lugares. |  |
|  | bspOnly | boolean |  | Se restringe los mercados de bsp únicamente, si es verdadero, o los mercados que no sean de bsp, si es falso. Si no se especifica, devuelve tanto los mercados BSP y los no BSP |  |
|  | turnInPlayEnabled | boolean |  | Restringe los mercados que cambiarán en juego si es verdadero o no cambiará en juego si es falso. Si no se especifica, devuelve ambos. |  |
|  | inPlayOnly | boolean |  | Restringe los mercados actualmente en juego si es verdadero o que no están actualmente en juego si es falso. Si no se especifica, devuelve ambos. |  |
|  | marketBettingTypes | Set
< MarketBettingType > |  | Restringe los mercados que coincidan con el tipo de apuestas del mercado (p. ej., Probabilidades, Hándicap asiático simple, Hándicap asiático doble o Línea) |  |
|  | marketCountries | Establecer<String> |  | Restringe los mercados que están en el país o los países especificados |  |
|  | marketTypeCodes | Establecer<String> |  | Restringe los mercados que coincidan con el tipo de mercado (es decir, MATCH_ODDS, HALF_TIME_SCORE). Debe utilizar esto en lugar de confiar en que el nombre del mercado, como los códigos del tipo de mercado, es el mismo en todos los idiomas |  |
|  | marketStartTime | TimeRange |  | Restringe los mercados con una hora de inicio de mercado antes o después de la fecha especificada |  |
|  | withOrders | Establecer< OrderStatus> |  | Restringe los mercados en los que tengo uno o más pedidos en este estado. |  |
|  |  |  |  |  |  |
| MarketCatalogue | MarketCatalogue | MarketCatalogue | MarketCatalogue | MarketCatalogue | MarketCatalogue |
| --- | --- | --- | --- | --- | --- |
|  | Información sobre el mercado | Información sobre el mercado | Información sobre el mercado | Información sobre el mercado |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | marketId | Cadena |  | El identificador único para el mercado. MarketId tiene el prefijo '1' o '2'. 1. = Exchange (Intercambio) del Reino Unido 2. = Exchange (Intercambio) de Australia |  |
|  | marketName | Cadena |  | El nombre del mercado |  |
|  | marketStartTime | Fecha |  | El momento en que comienza este mercado, solo se devuelve cuando se pasa la enumeración de MARKET_START_TIME en el marketProjections |  |
|  | description | MarketDescription |  | Detalles sobre el mercado |  |
|  | totalMatched | Double |  | La cantidad total de dinero que coincida en el mercado |  |
|  | runners | Lista<RunnerCatalogue> |  | Los corredores (selecciones) contenidos en el mercado |  |
|  | eventType | EventType |  | El tipo de evento en el que está contenido el mercado |  |
|  | competition | Competencia |  | La competencia en la que está contenida el mercado. Normalmente solo se aplica a las competencias de fútbol |  |
|  | event | Event |  | El evento en el que está contenido el mercado |  |
|  |  |  |  |  |  |
| MarketBook | MarketBook | MarketBook | MarketBook | MarketBook | MarketBook |
| --- | --- | --- | --- | --- | --- |
|  | Los datos dinámicos en un mercado | Los datos dinámicos en un mercado | Los datos dinámicos en un mercado | Los datos dinámicos en un mercado |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | marketId | Cadena |  | El identificador único para el mercado. MarketId tiene el prefijo '1' o '2'. 1. = Exchange (Intercambio) del Reino Unido 2. = Exchange (Intercambio) de Australia |  |
|  | isMarketDataDelayed | boolean |  | Verdadero si los datos devueltos por listMarketBook serán retrasados. Los datos pueden estar retrasados porque no ha iniciado sesión con una cuenta con fondos o si está utilizando una clave de aplicación que no permite datos actualizados. |  |
|  | status | MarketStatus |  | El estado del mercado, por ejemplo, ABIERTO, SUSPENDIDO CERRADO (asentado), etc. |  |
|  | betDelay | int |  | El número de segundos que se retiene un pedido hasta que se presenta en el mercado. Los pedidos generalmente se retrasan cuando el mercado está en juego |  |
|  | bspReconciled | boolean |  | Verdadero si el precio inicial del mercado se ha reconciliado |  |
|  | complete | boolean |  | Si es falso, los corredores se pueden agregar al mercado |  |
|  | inplay | boolean |  | Verdadero si el mercado está en juego actualmente |  |
|  | numberOfWinners | int |  | El número de selecciones que se podrían asentar como ganadoras |  |
|  | numberOfRunners | int |  | El número de corredores en el mercado |  |
|  | numberOfActiveRunners | int |  | El número de corredores que están actualmente activos. Un corredor activo es una selección disponible para apostar |  |
|  | lastMatchTime | Fecha |  | La hora más reciente en la que se ha ejecutado un pedido |  |
|  | totalMatched | double |  | El importe total que coincide |  |
|  | totalAvailable | double |  | La cantidad total de pedidos que permanecen sin coincidencia |  |
|  | crossMatching | boolean |  | Verdadero si la coincidencia cruzada está habilitada para este mercado. |  |
|  | runnersVoidable | boolean |  | Verdadero si los corredores en el mercado se pueden anular |  |
|  | version | long |  | La versión del mercado. La versión se incrementa cada vez que el mercado cambia de estado, por ejemplo, cambio en juego, o suspendido cuando se anota un gol. |  |
|  | runners | Lista<Runner> |  | Información acerca de los corredores (selecciones) en el mercado. |  |
|  |  |  |  |  |  |
| RunnerCatalogue | RunnerCatalogue | RunnerCatalogue | RunnerCatalogue | RunnerCatalogue | RunnerCatalogue |
| --- | --- | --- | --- | --- | --- |
|  | Información acerca de los corredores (selecciones) en un mercado | Información acerca de los corredores (selecciones) en un mercado | Información acerca de los corredores (selecciones) en un mercado | Información acerca de los corredores (selecciones) en un mercado |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | selectionId | long |  | El identificador único para la selección. |  |
|  | runnerName | Cadena |  | El nombre del corredor |  |
|  | handicap | double |  | El hándicap |  |
|  | sortPriority | int |  | La prioridad de orden de este corredor |  |
|  | metadata | Map<String,String> |  | Los metadatos asociados con el corredor. Para obtener una descripción de estos datos para las carreras de caballos, consulte Descripción de metadatos del corredor |  |
|  |  |  |  |  |  |
| Runner | Runner | Runner | Runner | Runner | Runner |
| --- | --- | --- | --- | --- | --- |
|  | Los datos dinámicos sobre los corredores en un mercado | Los datos dinámicos sobre los corredores en un mercado | Los datos dinámicos sobre los corredores en un mercado | Los datos dinámicos sobre los corredores en un mercado |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | selectionId | long |  | El identificador único del corredor (selección) |  |
|  | handicap | double |  | El hándicap. Introduzca el valor de hándicap específico (valor devuelto por el CORREDOR en listMaketBook) si el mercado es un mercado de hándicap asiático. |  |
|  | status | RunnerStatus |  | El estado de la selección (es decir, ACTIVO, RETIRADO, GANADOR, COLOCADO, PERDEDOR, OCULTO) Estado del corredor
La información está disponible durante 90 días después del asentamiento del mercado. |  |
|  | adjustmentFactor | double |  | El factor de ajuste aplicado si la selección se elimina |  |
|  | lastPriceTraded | double |  | El precio de la apuesta más reciente coincidente en esta selección |  |
|  | totalMatched | double |  | El importe total coincidente en este corredor |  |
|  | removalDate | Fecha |  | Si la fecha y la hora en la que se eliminó al corredor |  |
|  | sp | StartingPrices |  | Los precios relacionados del BSP para este corredor |  |
|  | ex | ExchangePrices |  | Los precios de Exchange (Intercambio) disponibles para este corredor |  |
|  | orders | Lista< Order > |  | Lista de pedidos en el mercado |  |
|  | matches | Lista< Match > |  | Lista de coincidencias (es decir, los pedidos que se han ejecutado de manera completa o parcial) |  |
|  | matchesByStrategy | Map<String,Matches> |  | Lista de coincidencias para cada estrategia, ordenada por datos coincidentes |  |
|  |  |  |  |  |  |
| StartingPrices | StartingPrices | StartingPrices | StartingPrices | StartingPrices | StartingPrices |
| --- | --- | --- | --- | --- | --- |
|  | Información sobre el precio inicial de Betfair. Solo disponible en los mercados BSP | Información sobre el precio inicial de Betfair. Solo disponible en los mercados BSP | Información sobre el precio inicial de Betfair. Solo disponible en los mercados BSP | Información sobre el precio inicial de Betfair. Solo disponible en los mercados BSP |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | nearPrice | double |  | Lo que sería el precio de inicio si el mercado se hubiera reconciliado ahora teniendo en cuenta las apuestas de SP así como las apuestas de intercambio sin coincidencia en la misma selección del intercambio. Estos datos se almacenan en caché y se actualizan cada 60 segundos. Tenga en cuenta lo siguiente: El tipo doble puede contener números, INF, -INF y NaN. |  |
|  | farPrice | double |  | Lo que sería el precio de inicio si el mercado se hubiera reconciliado ahora teniendo en cuenta únicamente las apuestas de SP actualmente realizadas. El precio lejano no es tan complicado, pero no tan preciso y solo representa el dinero en el intercambio en SP. Estos datos se almacenan en caché y se actualizan cada 60 segundos. Tenga en cuenta lo siguiente: El tipo doble puede contener números, INF, -INF y NaN. |  |
|  | backStakeTaken | Lista< PriceSize > |  | El importe total de las apuestas a favor coincidentes en el precio de inicio real de Betfair |  |
|  | layLiabilityTaken | Lista< PriceSize > |  | El importe en contra coincidente en el precio de inicio real de Betfair. |  |
|  | actualSP | double |  | El precio de BSP final para este corredor. Solo disponible para un mercado de BSP que se ha reconciliado. |  |
|  |  |  |  |  |  |
| ExchangePrices | ExchangePrices | ExchangePrices | ExchangePrices | ExchangePrices | ExchangePrices |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | availableToBack | Lista< PriceSize > |  |  |  |
|  | availableToLay | Lista< PriceSize > |  |  |  |
|  | tradedVolume | Lista< PriceSize > |  |  |  |
|  |  |  |  |  |  |
| Event | Event | Event | Event | Event | Event |
| --- | --- | --- | --- | --- | --- |
|  | Event | Event | Event | Event |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | id | Cadena |  | El identificador único para el evento |  |
|  | name | Cadena |  | El nombre del evento |  |
|  | countryCode | Cadena |  | El código de ISO-2 para el evento. Una lista de códigos ISO-2 está disponible a través de http://en.wikipedia.org/wiki/ISO_3166-1_alpha-2 |  |
|  | timezone | Cadena |  | Esta es la zona horaria en la que el evento se está realizando. |  |
|  | venue | Cadena |  | venue |  |
|  | openDate | Fecha |  | La fecha y hora programadas de inicio del evento. Esto es Europa/Londres (GMT) de manera predeterminada |  |
|  |  |  |  |  |  |
| EventResult | EventResult | EventResult | EventResult | EventResult | EventResult |
| --- | --- | --- | --- | --- | --- |
|  | Resultado de eventos | Resultado de eventos | Resultado de eventos | Resultado de eventos |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | event | Event |  | Event |  |
|  | marketCount | int |  | Recuento de mercados asociados con este evento |  |
|  |  |  |  |  |  |
| Competencia | Competencia | Competencia | Competencia | Competencia | Competencia |
| --- | --- | --- | --- | --- | --- |
|  | Competencia | Competencia | Competencia | Competencia |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | id | Cadena |  | id |  |
|  | name | Cadena |  | name |  |
|  |  |  |  |  |  |
| CompetitionResult | CompetitionResult | CompetitionResult | CompetitionResult | CompetitionResult | CompetitionResult |
| --- | --- | --- | --- | --- | --- |
|  | Resultado de la competencia | Resultado de la competencia | Resultado de la competencia | Resultado de la competencia |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | competition | Competencia |  | Competencia |  |
|  | marketCount | int |  | Recuento de mercados asociados con esta competencia |  |
|  | competitionRegion | Cadena |  | Región en la que esta competencia está sucediendo |  |
|  |  |  |  |  |  |
| EventType | EventType | EventType | EventType | EventType | EventType | EventType | EventType | EventType | EventType |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | EventType | EventType | EventType | EventType | EventType | EventType | EventType |  |  |
|  | Nombre de campo | Tipo | Tipo | Obligatorio | Obligatorio | Descripción | Descripción |  |  |
|  | id | Cadena | Cadena |  |  | id | id |  |  |
|  | name | Cadena | Cadena |  |  | name | name |  |  |
|  |  |  |  |  |  |  |  |  |  |
| EventTypeResult | EventTypeResult | EventTypeResult | EventTypeResult | EventTypeResult | EventTypeResult | EventTypeResult | EventTypeResult | EventTypeResult | EventTypeResult |
|  | Resultado de EventType | Resultado de EventType | Resultado de EventType | Resultado de EventType | Resultado de EventType | Resultado de EventType | Resultado de EventType | Resultado de EventType |  |
|  | Nombre de campo | Nombre de campo | Tipo | Tipo | Obligatorio | Obligatorio | Descripción | Descripción |  |
|  | eventType | eventType | EventType | EventType |  |  | El ID que identifica el tipo de evento | El ID que identifica el tipo de evento |  |
|  | marketCount | marketCount | int | int |  |  | Recuento de mercados asociados con este eventType | Recuento de mercados asociados con este eventType |  |
|  |  |  |  |  |  |  |  |  |  |
| MarketTypeResult | MarketTypeResult | MarketTypeResult | MarketTypeResult | MarketTypeResult | MarketTypeResult |
| --- | --- | --- | --- | --- | --- |
|  | Resultado de MarketType | Resultado de MarketType | Resultado de MarketType | Resultado de MarketType |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | marketType | Cadena |  | Tipo de mercado |  |
|  | marketCount | int |  | Recuento de mercados asociados con este marketType |  |
|  |  |  |  |  |  |
| CountryCodeResult | CountryCodeResult | CountryCodeResult | CountryCodeResult | CountryCodeResult | CountryCodeResult |
| --- | --- | --- | --- | --- | --- |
|  | Resultado de CountryCode | Resultado de CountryCode | Resultado de CountryCode | Resultado de CountryCode |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | countryCode | Cadena |  | El código de ISO-2 para el evento. Una lista de códigos ISO-2 está disponible a través de http://en.wi kipedia.org/wiki/ISO_3166-1_alpha-2 |  |
|  | marketCount | int |  | Recuento de mercados asociados con este código de país |  |
|  |  |  |  |  |  |
| VenueResult | VenueResult | VenueResult | VenueResult | VenueResult | VenueResult |
| --- | --- | --- | --- | --- | --- |
|  | Resultado del lugar | Resultado del lugar | Resultado del lugar | Resultado del lugar |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | venue | Cadena |  | Lugar |  |
|  | marketCount | int |  | Recuento de mercados asociados con este lugar |  |
|  |  |  |  |  |  |
| TimeRange | TimeRange | TimeRange | TimeRange | TimeRange | TimeRange |
| --- | --- | --- | --- | --- | --- |
|  | TimeRange | TimeRange | TimeRange | TimeRange |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | De | Fecha |  | De |  |
|  | a | Fecha |  | a |  |
|  |  |  |  |  |  |
| TimeRangeResult | TimeRangeResult | TimeRangeResult | TimeRangeResult | TimeRangeResult | TimeRangeResult |
| --- | --- | --- | --- | --- | --- |
|  | Resultado de TimeRange | Resultado de TimeRange | Resultado de TimeRange | Resultado de TimeRange |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | timeRange | TimeRange |  | TimeRange |  |
|  | marketCount | int |  | Recuento de mercados asociados con este TimeRange |  |
|  |  |  |  |  |  |
| Order | Order | Order | Order | Order | Order |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | betId | Cadena |  |  |  |
|  | orderType | OrderType |  | Tipo de pedido de BSP. |  |
|  | status | OrderStatus |  | EXECUTABLE (queda una cantidad sin coincidencia) o EXECUTION_COMPLETE (no queda ninguna cantidad sin coincidencia). |  |
|  | persistenceType | PersistenceType |  | Qué hacer con el pedido en el cambio en juego |  |
|  | side | Lado |  | Indica si la apuesta es a favor o en contra
Para los mercados de LÍNEA, los clientes compran una línea (apuesta en contra que gana si el resultado es superior a la línea tomada [precio]) o venden una línea (apuesta a favor que gana si el resultado es inferior a la línea tomada [precio]) |  |
|  | price | double |  | El precio de la apuesta. Tenga en cuenta lo siguiente: Los mercados de línea operan en probabilidades de dinero parejo de 2,0. Sin embargo, el precio de estos mercados se refiere a las ubicaciones de línea disponibles según lo definido por el rango mínimo - máximo de los mercados y los pasos de intervalo |  |
|  | size | double |  | El tamaño de la apuesta. |  |
|  | bspLiability | double |  | No debe confundirse con el tamaño. Este es el riesgo de una determinada apuesta de BSP. |  |
|  | placedDate | Fecha |  | La fecha, hasta el segundo, en la que se hizo la apuesta. |  |
|  | avgPriceMatched | double |  | El precio promedio con el que se coincidió. Los fragmentos coincidentes anulados se eliminan de este cálculo promedio. Para las apuestas de BSP MARKET_ON_CLOSE, esto informa el precio de SP coincidente después del proceso de reconciliación de SP. Este valor no es significativo para la actividad en los mercados de LÍNEA y no está garantizado que se devuelva o mantenga para estos mercados. |  |
|  | sizeMatched | double |  | La cantidad actual de esta apuesta que coincidió. |  |
|  | sizeRemaining | double |  | La cantidad actual de esta apuesta que no coincidió. |  |
|  | sizeLapsed | double |  | La cantidad actual de esta apuesta que caducó. |  |
|  | sizeCancelled | double |  | La cantidad actual de esta apuesta que se canceló. |  |
|  | sizeVoided | double |  | La cantidad actual de esta apuesta que se anuló. |  |
|  | customerOrderRef | CustomerOrderRef |  | La referencia de pedido de cliente enviada para esta apuesta |  |
|  | customerStrategyRef | CustomerStrategyRef |  | La referencia de estrategia de cliente enviada para esta apuesta |  |
|  |  |  |  |  |  |
| Match | Match | Match | Match | Match | Match |
| --- | --- | --- | --- | --- | --- |
|  | Una coincidencia de apuesta individual, o acumulación por precio o precio promedio. La acumulación depende del MatchProjection solicitado | Una coincidencia de apuesta individual, o acumulación por precio o precio promedio. La acumulación depende del MatchProjection solicitado | Una coincidencia de apuesta individual, o acumulación por precio o precio promedio. La acumulación depende del MatchProjection solicitado | Una coincidencia de apuesta individual, o acumulación por precio o precio promedio. La acumulación depende del MatchProjection solicitado |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | betId | Cadena |  | Solo está presente si no hay acumulación |  |
|  | matchId | Cadena |  | Solo está presente si no hay acumulación |  |
|  | side | Lado |  | Indica si la apuesta es a favor o en contra |  |
|  | price | double |  | El precio de coincidencia real o el precio de coincidencia promedio en función de la acumulación. Este valor no es significativo para la actividad en los mercados de LÍNEA y no está garantizado que se devuelva o mantenga para estos mercados. |  |
|  | size | double |  | El tamaño con el que se coincide en este fragmento, o este precio o precio promedio en función de la acumulación |  |
|  | matchDate | Fecha |  | Solo está presente si no hay acumulación |  |
|  |  |  |  |  |  |
| MarketVersion | MarketVersion | MarketVersion | MarketVersion | MarketVersion | MarketVersion |
| --- | --- | --- | --- | --- | --- |
|  | MarketVersion | MarketVersion | MarketVersion | MarketVersion |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | version | long |  | Un número creciente no monotónicamente que indica los cambios del mercado |  |
|  |  |  |  |  |  |
| MarketDescription | MarketDescription | MarketDescription | MarketDescription | MarketDescription | MarketDescription |
| --- | --- | --- | --- | --- | --- |
|  | MarketDefinition | MarketDefinition | MarketDefinition | MarketDefinition |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | persistenceEnabled | boolean |  | Si es ‘verdadero’, el mercado admite las apuestas ‘Mantener’ si el mercado cambiará en juego |  |
|  | bspMarket | boolean |  | Si es ‘verdadero’, el mercado admite la apuesta de SP de Betfair |  |
|  | marketTime | Fecha |  | La hora de inicio del mercado |  |
|  | suspendTime | Fecha |  | La hora de suspensión del mercado |  |
|  | settleTime | Fecha |  | La hora asentada |  |
|  | bettingType | MarketBettingType |  | Vea MarketBettingType |  |
|  | turnInPlayEnabled | boolean |  | Si es ‘verdadero’, el mercado se configura para cambiar en juego |  |
|  | marketType | Cadena |  | Tipo de base de mercado |  |
|  | regulator | Cadena |  | El regulador del mercado |  |
|  | marketBaseRate | double |  | La tasa de comisión aplicable al mercado |  |
|  | discountAllowed | boolean |  | Indica si se tiene en cuenta o no la tasa de descuento del usuario en este mercado. Si es ‘falso’, todos los usuarios se cambiarán a la misma tasa de comisión, independientemente de la tasa de descuento. |  |
|  | wallet | Cadena |  | La billetera a la que pertenece el mercado (Reino Unido/Australia) |  |
|  | rules | Cadena |  | Las reglas del mercado. |  |
|  | rulesHasDate | boolean |  |  |  |
|  | eachWayDivisor | double |  | El divisor se devuelve para marketType EACH_WAY únicamente y se refiere a la fracción de las probabilidades de ganar en la cual se asienta una parte de la colocación de una apuesta each way |  |
|  | clarifications | Cadena |  | Cualquier información adicional sobre el mercado |  |
|  |  |  |  |  |  |
| MarketRates | MarketRates | MarketRates | MarketRates | MarketRates | MarketRates | MarketRates |
| --- | --- | --- | --- | --- | --- | --- |
|  | MarketRates | MarketRates | MarketRates | MarketRates |  |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |  |
|  | marketBaseRate | double |  | marketBaseRate |  |  |
|  | discountAllowed | boolean |  | discountAllowed |  |  |
|  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |
| MarketLicence | MarketLicence | MarketLicence | MarketLicence | MarketLicence | MarketLicence | MarketLicence |
|  | MarketLicence | MarketLicence | MarketLicence | MarketLicence | MarketLicence |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción | Descripción |  |
|  | wallet | Cadena |  | La billetera de donde se tomarán los fondos al apostar en este mercado | La billetera de donde se tomarán los fondos al apostar en este mercado |  |
|  | rules | Cadena |  | Las reglas de este mercado | Las reglas de este mercado |  |
|  | rulesHasDate | boolean |  | La fecha y hora de inicio del mercado son pertinentes a las reglas. | La fecha y hora de inicio del mercado son pertinentes a las reglas. |  |
|  | clarifications | Cadena |  | Aclaraciones a las reglas para el mercado | Aclaraciones a las reglas para el mercado |  |
|  |  |  |  |  |  |  |
| MarketLineRangeInfo | MarketLineRangeInfo | MarketLineRangeInfo | MarketLineRangeInfo | MarketLineRangeInfo | MarketLineRangeInfo |
| --- | --- | --- | --- | --- | --- |
|  | Línea del mercado e información del rango | Línea del mercado e información del rango | Línea del mercado e información del rango | Línea del mercado e información del rango |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | maxUnitValue | double |  | maxPrice: valor máximo para el resultado, en las unidades 
de mercado para este mercado (p. ej., 100 carreras). |  |
|  | minUnitValue | double |  | minPrice: valor mínimo para el resultado, en las unidades 
de mercado para este mercado (p. ej., 0 carreras). |  |
|  | interval | double |  | interval: la escalera de probabilidades en este mercado será entre el rango de minUnitValue y maxUnitValue, en incrementos del valor de intervalo. Por ejemplo: si minUnitValue=10 carreras, maxUnitValue=20 carreras, interval=0,5 carreras, las probabilidades válidas incluyen 10, 10.5, 11, 11.5 hasta 20 carreras. |  |
|  | marketUnit | Cadena |  | unit: el tipo de unidad en el que son incrementadas las líneas por el intervalo (p. ej.: carreras, goles o segundos). |  |
|  |  |  |  |  |  |
| PriceSize | PriceSize | PriceSize | PriceSize | PriceSize | PriceSize |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | price | double |  | El precio disponible |  |
|  | size | double |  | La apuesta disponible |  |
|  |  |  |  |  |  |
| ClearedOrderSummary | ClearedOrderSummary | ClearedOrderSummary | ClearedOrderSummary | ClearedOrderSummary | ClearedOrderSummary |
| --- | --- | --- | --- | --- | --- |
|  | Resumen de un pedido hecho. | Resumen de un pedido hecho. | Resumen de un pedido hecho. | Resumen de un pedido hecho. |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | eventTypeId | EventTypeId |  | El ID del tipo de la apuesta de tipo de evento. Disponible en el nivel EVENT_TYPE groupBy o inferior. |  |
|  | eventId | EventId |  | El ID de la apuesta de evento. Disponible en el nivel EVENT groupBy o inferior. |  |
|  | marketId | MarketId |  | El ID de la apuesta del mercado. Disponible en el nivel MARKET groupBy o inferior. |  |
|  | selectionId | SelectionId |  | El ID de la apuesta de selección. Disponible en el nivel RUNNER groupBy o inferior. |  |
|  | Hándicap | Hándicap |  | El hándicap. Introduzca el valor de hándicap específico (valor devuelto por el CORREDOR en listMaketBook) si el mercado es un mercado de hándicap asiático. Disponible en el nivel MARKET groupBy o inferior. |  |
|  | betId | BetId |  | El ID de la apuesta. Disponible en el nivel BET GroupBy. |  |
|  | placedDate | Fecha |  | La fecha en la que el cliente hizo el pedido de apuesta. Solo disponible en el nivel BET groupBy. |  |
|  | persistenceType | PersistenceType |  | El estado de persistencia de cambio en juego del pedido a la hora de realizar la apuesta. Este campo estará vacío o se omitirá en apuestas de SP verdaderas. Solo disponible en el nivel BET groupBy. |  |
|  | orderType | OrderType |  | El tipo de apuesta (por ejemplo, apuesta de Exchange de riesgo limitado estándar [LIMIT], una apuesta de BSP estándar [MARKET_ON_CLOSE], o una apuesta de BSP de precio mínimo aceptado [LIMIT_ON_CLOSE]). Si la apuesta tiene un OrderType de MARKET_ON_CLOSE y un persistenceType de MARKET_ON_CLOSE, entonces es una apuesta que ha cambiado de LIMIT a MARKET_ON_CLOSE. Solo disponible en el nivel BET groupBy. |  |
|  | Lado | Lado |  | Independientemente de si la apuesta era a favor o en contra. Disponible en el nivel SIDE groupBy o inferior. |  |
|  | itemDescription | ItemDescription |  | Un contenedor para todos los datos auxiliares y el texto localizado válidos para este elemento |  |
|  | betOutcome | Cadena |  | El resultado del asentamiento de la apuesta. Tres estados (GANAR/PERDER/COLOCAR) para dar cuenta de las apuestas Each Way donde la parte de la colocación de la apuesta ganó, pero la parte ganadora perdió. El importe de pérdida/ganancia en este caso podría ser positivo o negativo según el precio que coincida. Solo disponible en el nivel BET groupBy. |  |
|  | priceRequested | Precio |  | El promedio de precio solicitado en todos los pedidos de apuesta asentada en relación con este elemento. Disponible en el nivel SIDE groupBy o inferior. Para mercados LÍNEA esta es la posición de la línea solicitada. Para mercados LÍNEA esta es la posición de la línea solicitada. |  |
|  | settledDate | Fecha |  | La fecha y hora en que Betfair asentó el pedido de apuesta. Disponible en el nivel SIDE groupBy o inferior. |  |
|  | lastMatchedDate | Fecha |  | La fecha y hora en que Betfair aplicó la coincidencia del último pedido de apuesta. Disponible en los pedidos asentados únicamente. |  |
|  | betCount | int |  | El número de apuestas reales dentro de esta agrupación (será 1 para APOSTAR GroupBy) |  |
|  | commission | Size |  | El importe acumulado de la comisión pagado por el cliente a través de todas las apuestas en relación con este elemento, en la moneda de la cuenta.
Disponible únicamente en los grupos de nivel de EXCHANGE, EVENT_TYPE, EVENT y MARKET. |  |
|  | priceMatched | Precio |  | El promedio de precio coincidente en todas las apuestas asentadas o en los fragmentos de apuestas en relación con este elemento. Disponible en el nivel SIDE groupBy o inferior. Para mercados LÍNEA esta es la posición de la línea que coincide. |  |
|  | priceReduced | boolean |  | Si es verdadero, el precio coincidente se vio afectado por un factor de reducción debido a la eliminación de un corredor del mercado de carreras de caballos. |  |
|  | sizeSettled | Size |  | El tamaño de la apuesta acumulada que se asentó como coincidente o anulada en relación con este tema, en la moneda de la cuenta. Disponible en el nivel SIDE groupBy o inferior. |  |
|  | profit | Size |  | La ganancia o pérdida (ganancia negativa) obtenida en esta línea, en la moneda de la cuenta |  |
|  | sizeCancelled | Size |  | La cantidad de la apuesta que estaba disponible para la coincidencia, antes de la cancelación o la caducidad, en la moneda de la cuenta |  |
|  | customerOrderRef | Cadena |  | La referencia de pedido que define el cliente para el pedido de la apuesta |  |
|  | customerStrategyRef | Cadena |  | La referencia de estrategia que define el cliente para el pedido de la apuesta |  |
|  |  |  |  |  |  |
| ClearedOrderSummaryReport | ClearedOrderSummaryReport | ClearedOrderSummaryReport | ClearedOrderSummaryReport | ClearedOrderSummaryReport | ClearedOrderSummaryReport |
| --- | --- | --- | --- | --- | --- |
|  | Un contenedor que representa los resultados de la búsqueda. | Un contenedor que representa los resultados de la búsqueda. | Un contenedor que representa los resultados de la búsqueda. | Un contenedor que representa los resultados de la búsqueda. |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | clearedOrders | Lista<ClearedOrderSummary> |  | La lista de pedidos hechos devuelta por la consulta. Esta será una lista válida 
(es decir, vacío o no vacío, pero nunca ‘nulo'). |  |
|  | moreAvailable | boolean |  | Indica si hay más elementos de resultados más allá de esta página. Tenga en cuenta que los datos subyacentes son altamente dependientes del tiempo y la consulta de pedidos de búsqueda siguiente puede devolver un resultado vacío. |  |
|  |  |  |  |  |  |
| ItemDescription | ItemDescription | ItemDescription | ItemDescription | ItemDescription | ItemDescription |
| --- | --- | --- | --- | --- | --- |
|  | Este objeto contiene algunos textos que pueden ser útiles para representar una vista del historial de apuestas. No ofrece ninguna garantía a largo plazo en cuanto a la exactitud del texto. | Este objeto contiene algunos textos que pueden ser útiles para representar una vista del historial de apuestas. No ofrece ninguna garantía a largo plazo en cuanto a la exactitud del texto. | Este objeto contiene algunos textos que pueden ser útiles para representar una vista del historial de apuestas. No ofrece ninguna garantía a largo plazo en cuanto a la exactitud del texto. | Este objeto contiene algunos textos que pueden ser útiles para representar una vista del historial de apuestas. No ofrece ninguna garantía a largo plazo en cuanto a la exactitud del texto. |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | eventTypeDesc | Cadena |  | El nombre del tipo de evento, traducido en el idioma solicitado. Disponible en EVENT_TYPE groupBy o inferior. |  |
|  | eventDesc | Cadena |  | eventName o openDate + venue, traducidos en el idioma solicitado. Disponible en EVENT groupBy o inferior. |  |
|  | marketDesc | Cadena |  | El nombre del mercado o tipo de mercado de carreras (”Ganar”, “Para que se coloque [2 lugares]”, “Para que se coloque 
[5 lugares]”, etc.) que se tradujeron en el idioma solicitado. Disponible en MARKET groupBy o inferior. |  |
|  | marketType | Cadena |  | El tipo de mercado, por ejemplo, MATCH_ODDS, PLACE, 
WIN etc. |  |
|  | marketStartTime | Fecha |  | La hora de inicio del mercado (en formato ISO-8601, no traducido). Disponible en MARKET groupBy o inferior. |  |
|  | runnerDesc | Cadena |  | El nombre del corredor, tal vez incluye el hándicap, traducido en el idioma solicitado. Disponible en BET groupBy. |  |
|  | numberOfWinners | int |  | El número de ganadores en un mercado. Disponible en BET groupBy. |  |
|  | eachWayDivisor | double |  | El divisor se devuelve para marketType EACH_WAY únicamente y se refiere a la fracción de las probabilidades de ganar en la cual se asienta una parte de la colocación de una apuesta each way |  |
|  |  |  |  |  |  |
| RunnerID | RunnerID | RunnerID | RunnerID | RunnerID | RunnerID |
| --- | --- | --- | --- | --- | --- |
|  | Este objeto contiene el identificador único de un corredor | Este objeto contiene el identificador único de un corredor | Este objeto contiene el identificador único de un corredor | Este objeto contiene el identificador único de un corredor |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | marketId | MarketId |  | El ID de la apuesta del mercado |  |
|  | selectionId | SelectionId |  | El ID de la apuesta de selección |  |
|  | handicap | Hándicap |  | El hándicap asociado con el corredor en el caso de mercados de hándicap asiático, de lo contrario devuelve ‘0,0'. |  |
|  |  |  |  |  |  |
| CurrentOrderSummaryReport | CurrentOrderSummaryReport | CurrentOrderSummaryReport | CurrentOrderSummaryReport | CurrentOrderSummaryReport | CurrentOrderSummaryReport |
| --- | --- | --- | --- | --- | --- |
|  | Un contenedor que representa los resultados de la búsqueda. | Un contenedor que representa los resultados de la búsqueda. | Un contenedor que representa los resultados de la búsqueda. | Un contenedor que representa los resultados de la búsqueda. |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | currentOrders | Lista< CurrentOrderSummary > |  | La lista de pedidos actuales devuelta por la consulta. Esta será una lista válida (es decir, vacío o no vacío, pero nunca ‘nulo'). |  |
|  | moreAvailable | boolean |  | Indica si hay más elementos de resultados más allá de esta página. Tenga en cuenta que los datos subyacentes son altamente dependientes del tiempo y la consulta de pedidos de búsqueda siguiente puede devolver un resultado vacío. |  |
|  |  |  |  |  |  |
| CurrentOrderSummary | CurrentOrderSummary | CurrentOrderSummary | CurrentOrderSummary | CurrentOrderSummary | CurrentOrderSummary |
| --- | --- | --- | --- | --- | --- |
|  | Resumen de un pedido actual. | Resumen de un pedido actual. | Resumen de un pedido actual. | Resumen de un pedido actual. |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | betId | Cadena |  | El ID de apuesta del pedido de colocación original. |  |
|  | marketId | Cadena |  | El ID del mercado para el que se hace el pedido. |  |
|  | selectionId | long |  | El ID de selección para la que se hace el pedido. |  |
|  | handicap | double |  | El hándicap asociado con el corredor en el caso de mercados de hándicap asiático, de lo contrario devuelve nulo. |  |
|  | priceSize | PriceSize |  | El precio y el tamaño de la apuesta. |  |
|  | bspLiability | double |  | No debe confundirse con el tamaño. Este es el riesgo de una determinada apuesta de BSP. |  |
|  | Lado | Lado |  | A FAVOR/EN CONTRA |  |
|  | status | OrderStatus |  | EXECUTABLE (queda una cantidad sin coincidencia) o EXECUTION_COMPLETE (no queda ninguna cantidad sin coincidencia). |  |
|  | persistenceType | PersistenceType |  | Qué hacer con el pedido en el cambio en juego. |  |
|  | orderType | OrderType |  | Tipo de pedido de BSP. |  |
|  | placedDate | Fecha |  | La fecha, hasta el segundo, en la que se hizo la apuesta. |  |
|  | matchedDate | Fecha |  | La fecha, hasta el segundo, del último fragmento de apuesta coincidente (donde aplique) |  |
|  | averagePriceMatched | double |  | El precio promedio con el que se coincidió. Los fragmentos coincidentes anulados se eliminan de este cálculo promedio. El precio se ajusta automáticamente en caso de no haber corredores declarados con factores de reducción aplicables. Tenga en cuenta lo siguiente: Este valor no es significativo para la actividad en los mercados de LÍNEA y no está garantizado que se devuelva o mantenga para estos mercados. |  |
|  | sizeMatched | double |  | La cantidad actual de esta apuesta que coincidió. |  |
|  | sizeRemaining | double |  | La cantidad actual de esta apuesta que no coincidió. |  |
|  | sizeLapsed | double |  | La cantidad actual de esta apuesta que caducó. |  |
|  | sizeCancelled | double |  | La cantidad actual de esta apuesta que se canceló. |  |
|  | sizeVoided | double |  | La cantidad actual de esta apuesta que se anuló. |  |
|  | regulatorAuthCode | Cadena |  | El código de autorización del regulador. |  |
|  | regulatorCode | Cadena |  | El código del regulador. |  |
|  | customerOrderRef | Cadena |  | La referencia de pedido que define el cliente para la apuesta |  |
|  | customerStrategyRef | Cadena |  | La referencia de estrategia que define el cliente para la apuesta |  |
|  |  |  |  |  |  |
| PlaceInstruction | PlaceInstruction | PlaceInstruction | PlaceInstruction | PlaceInstruction | PlaceInstruction |
| --- | --- | --- | --- | --- | --- |
|  | Instrucción para realizar un nuevo pedido | Instrucción para realizar un nuevo pedido | Instrucción para realizar un nuevo pedido | Instrucción para realizar un nuevo pedido |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | orderType | OrderType |  |  |  |
|  | selectionId | long |  | El selection_id. |  |
|  | handicap | double |  | El hándicap asociado con el corredor en el caso de mercados de hándicap asiático (p. ej., marketTypes ASIAN_HANDICAP_DOUBLE_LINE, ASIAN_HANDICAP_SINGLE_LINE), de lo contrario devuelve nulo. |  |
|  | side | Lado |  | A favor o en contra |  |
|  | limitOrder | LimitOrder |  | Una simple apuesta de intercambio de ejecución inmediata |  |
|  | limitOnCloseOrder | LimitOnCloseOrder |  | Las apuestas coincidirán si, y solo si, el precio inicial devuelto es mejor que un precio especificado. En el caso de apuestas a favor, las apuestas de LOC coinciden si el precio inicial calculado es mayor que el precio especificado. En el caso de apuestas a favor, las apuestas de LOC coinciden si el precio inicial es menor que el precio especificado. Si el límite especificado es igual al precio inicial, entonces puede coincidir, coincidir parcialmente, o no coincidir en absoluto, en función de cuánto se necesita para equilibrar todas las apuestas con respecto a cada una (MOC, LOC y apuestas de intercambio normal) |  |
|  | marketOnCloseOrder | MarketOnCloseOrder |  | Las apuestas siguen sin coincidir hasta que el mercado se haya reconciliado. Coinciden y se asientan a un precio representativo del mercado en el momento en el mercado cambia en juego. El mercado se reconcilia para encontrar un precio inicial y las apuestas de MOC se asientan a cualquier precio inicial devuelto. Las apuestas de MOC siempre coinciden y están asentadas, a menos que no haya un precio inicial disponible para la selección. El mercado de apuestas cerradas solo se puede colocar antes de determinar el precio inicial |  |
|  | customerOrderRef | Cadena |  | Una referencia opcional que los clientes pueden establecer para identificar instrucciones. No se hará ninguna validación sobre la exclusividad y la cadena está limitada a 32 caracteres. Si se proporciona una cadena vacía, se considerará nula. |  |
|  |  |  |  |  |  |
| PlaceExecutionReport | PlaceExecutionReport | PlaceExecutionReport | PlaceExecutionReport | PlaceExecutionReport | PlaceExecutionReport |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | customerRef | Cadena |  | Eco de customerRef si se pasa. |  |
|  | status | ExecutionReportStatus |  |  |  |
|  | errorCode | ExecutionReportErrorCode |  |  |  |
|  | marketId | Cadena |  | Eco de marketId pasado |  |
|  | instructionReports | Lista< PlaceInstructionReport > |  |  |  |
|  |  |  |  |  |  |
| LimitOrder | LimitOrder | LimitOrder | LimitOrder | LimitOrder | LimitOrder |
| --- | --- | --- | --- | --- | --- |
|  | Coloque un nuevo pedido de LÍMITE (simple apuesta de intercambio para ejecución inmediata) | Coloque un nuevo pedido de LÍMITE (simple apuesta de intercambio para ejecución inmediata) | Coloque un nuevo pedido de LÍMITE (simple apuesta de intercambio para ejecución inmediata) | Coloque un nuevo pedido de LÍMITE (simple apuesta de intercambio para ejecución inmediata) |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | size | double |  | El tamaño de la apuesta. Tenga en cuenta lo siguiente: Para el tipo de mercado EACH_WAY. 
La apuesta total = tamaño x 2 |  |
|  | price | double |  | El precio límite. Para los mercados de LÍNEA, el precio en el que se asienta y se logra la apuesta siempre será 2,0 (parejo). En estas apuestas, el campo Price (Precio) se utiliza para indicar el valor de línea que se compra o se vende |  |
|  | persistenceType | PersistenceType |  | Qué hacer con el pedido en el cambio en juego |  |
|  | timeInForce | TimeInForce |  | El tipo de valor TimeInForce que se debe utilizar. Este valor prevalece sobre cualquier valor PersistenceType elegido.
Si este atributo se completa junto con el campo PersistenceType, el PersistenceType será ignorado. Cuando utilice FILL_OR_KILL para un mercado de línea, se desactiva la funcionalidad de precio promedio ponderado por volumen (VWAP) |  |
|  | minFillSize | Size |  | Un campo opcional utilizado si el atributo TimeInForce está completado. Si se especifica sin TimeInForce, entonces se ignora este campo.
Si no se especifica ningún minFillSize, el pedido se elimina, a menos que coincida todo el tamaño.
Si se especifica minFillSize, el pedido se elimina, excepto si al menos se puede hacer coincidir minFillSize. minFillSize no puede ser mayor que el tamaño del pedido. Si se especifica para un pedido de BetTargetType y FILL_OR_KILL, entonces este valor será ignorado |  |
|  | betTargetType | BetTargetType |  | Un campo opcional para permitir apostar a un PAYOUT o BACKERS_PROFIT determinado.
No es válido especificar un Size y BetTargetType. 
La coincidencia brinda la mejor ejecución al precio solicitado o lo mejor hasta el pago o ganancia.
Si la apuesta no coincide por completo y de inmediato, la parte restante entra en el grupo de apuestas sin coincidencia en el intercambio
Las apuestas de BetTargetType no son válidas para mercados de LÍNEA |  |
|  | betTargetSize | Size |  | Un campo opcional que se debe determinar si BetTargetType se especifica para este pedido.
El tamaño de resultado solicitado del pago o ganancia. Esto se nombra desde el punto de vista del apostador a favor. Para las apuestas en contra, la ganancia representa el riesgo de la apuesta |  |
|  |  |  |  |  |  |
| LimitOnCloseOrder | LimitOnCloseOrder | LimitOnCloseOrder | LimitOnCloseOrder | LimitOnCloseOrder | LimitOnCloseOrder |
| --- | --- | --- | --- | --- | --- |
|  | Haga una nueva apuesta de LIMIT_ON_CLOSE | Haga una nueva apuesta de LIMIT_ON_CLOSE | Haga una nueva apuesta de LIMIT_ON_CLOSE | Haga una nueva apuesta de LIMIT_ON_CLOSE |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | riesgo | double |  | El tamaño de la apuesta. |  |
|  | price | double |  | El precio límite de la apuesta si es LOC |  |
|  |  |  |  |  |  |
| MarketOnCloseOrder | MarketOnCloseOrder | MarketOnCloseOrder | MarketOnCloseOrder | MarketOnCloseOrder | MarketOnCloseOrder |
| --- | --- | --- | --- | --- | --- |
|  | Haga una nueva apuesta de MARKET_ON_CLOSE | Haga una nueva apuesta de MARKET_ON_CLOSE | Haga una nueva apuesta de MARKET_ON_CLOSE | Haga una nueva apuesta de MARKET_ON_CLOSE |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | riesgo | double |  | El tamaño de la apuesta. |  |
|  |  |  |  |  |  |
| PlaceInstructionReport | PlaceInstructionReport | PlaceInstructionReport | PlaceInstructionReport | PlaceInstructionReport | PlaceInstructionReport |
| --- | --- | --- | --- | --- | --- |
|  | Respuesta a una PlaceInstruction | Respuesta a una PlaceInstruction | Respuesta a una PlaceInstruction | Respuesta a una PlaceInstruction |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | status | InstructionReportStatus |  | Independientemente de si el comando tuvo éxito o no. |  |
|  | errorCode | InstructionReportErrorCode |  | causa de la falla, o nulo si el comando tiene éxito |  |
|  | orderStatus | OrderStatus |  | El estado del pedido, si la instrucción 
es correcta.
Si la instrucción no fue satisfactoria, 
no se proporciona ningún valor. |  |
|  | instruction | PlaceInstruction |  | La instrucción que se solicitó |  |
|  | betId | Cadena |  | El ID de apuesta de la nueva apuesta. Será nulo en caso de error o si el pedido se realizó de forma asincrónica. |  |
|  | placedDate | Fecha |  | Será nulo si el pedido se realizó de forma asincrónica. |  |
|  | averagePriceMatched | Precio |  | Será nulo si el pedido se realizó de forma asincrónica. Este valor no es significativo para la actividad en los mercados de LÍNEA y no está garantizado que se devuelva o mantenga para estos mercados. |  |
|  | sizeMatched | Size |  | Será nulo si el pedido se realizó de forma asincrónica. |  |
|  |  |  |  |  |  |
| CancelInstruction | CancelInstruction | CancelInstruction | CancelInstruction | CancelInstruction | CancelInstruction |
| --- | --- | --- | --- | --- | --- |
|  | Instrucciones para cancelar total o parcialmente un pedido (solo se aplica a los pedidos de LÍMITE) | Instrucciones para cancelar total o parcialmente un pedido (solo se aplica a los pedidos de LÍMITE) | Instrucciones para cancelar total o parcialmente un pedido (solo se aplica a los pedidos de LÍMITE) | Instrucciones para cancelar total o parcialmente un pedido (solo se aplica a los pedidos de LÍMITE) |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | betId | Cadena |  | El betId |  |
|  | sizeReduction | double |  | Si se suministra, es una cancelación parcial. Debe establecerse 
en ‘nulo’ si no se requiere la reducción de tamaño. |  |
|  |  |  |  |  |  |
| CancelExecutionReport | CancelExecutionReport | CancelExecutionReport | CancelExecutionReport | CancelExecutionReport | CancelExecutionReport |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | customerRef | Cadena |  | Eco de customerRef si se pasa. |  |
|  | status | ExecutionReportStatus |  |  |  |
|  | errorCode | ExecutionReportErrorCode |  |  |  |
|  | marketId | Cadena |  | Eco de marketId pasado |  |
|  | instructionReports | Lista< CancelInstructionReport > |  |  |  |
|  |  |  |  |  |  |
| ReplaceInstruction | ReplaceInstruction | ReplaceInstruction | ReplaceInstruction | ReplaceInstruction | ReplaceInstruction |
| --- | --- | --- | --- | --- | --- |
|  | Instrucciones para sustituir un pedido LIMIT o LIMIT_ON_CLOSE a un nuevo precio. Se cancelará el pedido original y se hará un nuevo pedido con el nuevo precio para el resto de la apuesta. | Instrucciones para sustituir un pedido LIMIT o LIMIT_ON_CLOSE a un nuevo precio. Se cancelará el pedido original y se hará un nuevo pedido con el nuevo precio para el resto de la apuesta. | Instrucciones para sustituir un pedido LIMIT o LIMIT_ON_CLOSE a un nuevo precio. Se cancelará el pedido original y se hará un nuevo pedido con el nuevo precio para el resto de la apuesta. | Instrucciones para sustituir un pedido LIMIT o LIMIT_ON_CLOSE a un nuevo precio. Se cancelará el pedido original y se hará un nuevo pedido con el nuevo precio para el resto de la apuesta. | Instrucciones para sustituir un pedido LIMIT o LIMIT_ON_CLOSE a un nuevo precio. Se cancelará el pedido original y se hará un nuevo pedido con el nuevo precio para el resto de la apuesta. |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | betId | Cadena |  | Identificador único de la apuesta |  |
|  | newPrice | double |  | El precio para reemplazar 
la apuesta |  |
|  |  |  |  |  |  |
| ReplaceExecutionReport | ReplaceExecutionReport | ReplaceExecutionReport | ReplaceExecutionReport | ReplaceExecutionReport | ReplaceExecutionReport |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | customerRef | Cadena |  | Eco de customerRef si se pasa. |  |
|  | status | ExecutionReportStatus |  |  |  |
|  | errorCode | ExecutionReportErrorCode |  |  |  |
|  | marketId | Cadena |  | Eco de marketId pasado |  |
|  | instructionReports | Lista< ReplaceInstructionReport > |  |  |  |
|  |  |  |  |  |  |
| ReplaceInstructionReport | ReplaceInstructionReport | ReplaceInstructionReport | ReplaceInstructionReport | ReplaceInstructionReport | ReplaceInstructionReport |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | status | InstructionReportStatus |  | Independientemente de si el comando tuvo éxito o no. |  |
|  | errorCode | InstructionReportErrorCode |  | causa de la falla, o nulo si el comando tiene éxito |  |
|  | cancelInstructionReport | CancelInstructionReport |  | Informe de cancelación para el pedido original |  |
|  | placeInstructionReport | PlaceInstructionReport |  | Informe de colocación para el nuevo pedido |  |
|  |  |  |  |  |  |
| CancelInstructionReport | CancelInstructionReport | CancelInstructionReport | CancelInstructionReport | CancelInstructionReport | CancelInstructionReport |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | status | InstructionReportStatus |  | Independientemente de si el comando tuvo éxito o no. |  |
|  | errorCode | InstructionReportErrorCode |  | causa de la falla, o nulo si el comando tiene éxito |  |
|  | instruction | CancelInstruction |  | La instrucción que se solicitó |  |
|  | sizeCancelled | double |  |  |  |
|  | cancelledDate | Fecha |  |  |  |
|  |  |  |  |  |  |
| UpdateInstruction | UpdateInstruction | UpdateInstruction | UpdateInstruction | UpdateInstruction | UpdateInstruction |
| --- | --- | --- | --- | --- | --- |
|  | Instrucciones para actualizar la persistencia de la apuesta de LÍMITE de un pedido que no afecta la exposición | Instrucciones para actualizar la persistencia de la apuesta de LÍMITE de un pedido que no afecta la exposición | Instrucciones para actualizar la persistencia de la apuesta de LÍMITE de un pedido que no afecta la exposición | Instrucciones para actualizar la persistencia de la apuesta de LÍMITE de un pedido que no afecta la exposición |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | betId | Cadena |  | Identificador único de la apuesta |  |
|  | newPersistenceType | PersistenceType |  | El nuevo tipo de persistencia a la cual actualizar esta apuesta |  |
|  |  |  |  |  |  |
| UpdateExecutionReport | UpdateExecutionReport | UpdateExecutionReport | UpdateExecutionReport | UpdateExecutionReport | UpdateExecutionReport | UpdateExecutionReport | UpdateExecutionReport | UpdateExecutionReport | UpdateExecutionReport |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |
|  | Nombre de campo | Nombre de campo | Tipo | Tipo | Obligatorio | Obligatorio | Descripción |  |  |
|  | customerRef | customerRef | Cadena | Cadena |  |  | Eco de customerRef si se pasa. |  |  |
|  | status | status | ExecutionReportStatus | ExecutionReportStatus |  |  |  |  |  |
|  | errorCode | errorCode | ExecutionReportErrorCode | ExecutionReportErrorCode |  |  |  |  |  |
|  | marketId | marketId | Cadena | Cadena |  |  | Eco de marketId pasado |  |  |
|  | instructionReports | instructionReports | Lista< UpdateInstructionReport > | Lista< UpdateInstructionReport > |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| UpdateInstruction | UpdateInstruction | UpdateInstruction | UpdateInstruction | UpdateInstruction | UpdateInstruction | UpdateInstruction | UpdateInstruction | UpdateInstruction | UpdateInstruction |
|  |  |  |  |  |  |  |  |  |  |
|  | Nombre de campo | Tipo | Tipo | Obligatorio | Obligatorio | Descripción | Descripción | Descripción |  |
|  | status | InstructionReportStatus | InstructionReportStatus |  |  | Independientemente de si el comando tuvo éxito o no. | Independientemente de si el comando tuvo éxito o no. | Independientemente de si el comando tuvo éxito o no. |  |
|  | errorCode | InstructionReportErrorCode | InstructionReportErrorCode |  |  | causa de la falla, o nulo si el comando tiene éxito | causa de la falla, o nulo si el comando tiene éxito | causa de la falla, o nulo si el comando tiene éxito |  |
|  | instruction | UpdateInstruction | UpdateInstruction |  |  | La instrucción que se solicitó | La instrucción que se solicitó | La instrucción que se solicitó |  |
|  |  |  |  |  |  |  |  |  |  |
| PriceProjection | PriceProjection | PriceProjection | PriceProjection | PriceProjection | PriceProjection |
| --- | --- | --- | --- | --- | --- |
|  | Criterios de selección de los datos de precios de retorno | Criterios de selección de los datos de precios de retorno | Criterios de selección de los datos de precios de retorno | Criterios de selección de los datos de precios de retorno |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | priceData | Establecer< PriceData > |  | Los datos de precios básicos que desea recibir en la respuesta. |  |
|  | exBestOffersOverrides | ExBestOffersOverrides |  | Opciones para modificar la representación predeterminada de mejores precios de oferta aplicables a la selección EX_BEST_OFFERS priceData |  |
|  | virtualise | boolean |  | Indica si los precios devueltos deben incluir precios virtuales. Aplicable a las selecciones de EX_BEST_OFFERS y EX_ALL_OFFERS priceData, el valor predeterminado es falso. |  |
|  | rolloverStakes | boolean |  | Indica si el volumen devuelto en cada punto de precio debe ser el valor absoluto o la suma acumulada de los volúmenes disponibles en el precio y todos los mejores precios. Si no se especifica, el valor predeterminado es falso. Se aplica a las proyecciones de precios de EX_BEST_OFFERS y EX_ALL_OFFERS. Todavía no se admite. |  |
|  |  |  |  |  |  |
| ExBestOffersOverrides | ExBestOffersOverrides | ExBestOffersOverrides | ExBestOffersOverrides | ExBestOffersOverrides | ExBestOffersOverrides |
| --- | --- | --- | --- | --- | --- |
|  | Opciones para modificar la representación predeterminada de los mejores precios de oferta. | Opciones para modificar la representación predeterminada de los mejores precios de oferta. | Opciones para modificar la representación predeterminada de los mejores precios de oferta. | Opciones para modificar la representación predeterminada de los mejores precios de oferta. |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | bestPricesDepth | int |  | El número máximo de precios para devolver en cada lado de cada corredor. Si no se especifica, el valor predeterminado es 3. La máxima profundidad de precio devuelto es 10. |  |
|  | rollupModel | RollupModel |  | El modelo que se debe utilizar al acumular los tamaños disponibles. Si no se especifica, el valor queda predeterminado en modelo de acumulación de APUESTA con rollupLimit de apuesta mínima en la moneda especificada. |  |
|  | rollupLimit | int |  | El límite de volumen que se debe usar al acumular los tamaños devueltos. La definición exacta del límite depende de rollupModel. Si no hay ningún límite proporcionado, se utiliza la apuesta mínima como valor predeterminado. Se omite si no se especifica ningún modelo de acumulación. |  |
|  | rollupLiabilityThreshold | double |  | Solo se aplica cuando rollupModel es MANAGED_LIABILITY. El modelo de acumulación pasa de estar basado en la apuesta a basarse en el riesgo al precio de apuesta en contra más bajo que es >= el nivel predeterminado de rollupLiabilityThreshold.service (TBD). Todavía no se admite. |  |
|  | rollupLiabilityFactor | int |  | Solo se aplica cuando rollupModel es MANAGED_LIABILITY. (rollupLiabilityFactor * rollupLimit) es el riesgo mínimo con el que el usuario se considera conforme. Después del precio de rollupLiabilityThreshold, se acumularán los volúmenes subsiguientes hasta un valor mínimo de manera que el riesgo sea >= el valor predeterminado de nivel de liability.service mínimo (5). Todavía no se admite. |  |
|  |  |  |  |  |  |
| MarketProfitAndLoss | MarketProfitAndLoss | MarketProfitAndLoss | MarketProfitAndLoss | MarketProfitAndLoss | MarketProfitAndLoss |
| --- | --- | --- | --- | --- | --- |
|  | Ganancias y pérdidas en un mercado | Ganancias y pérdidas en un mercado | Ganancias y pérdidas en un mercado | Ganancias y pérdidas en un mercado |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | marketId | Cadena |  | El identificador único para el mercado |  |
|  | commissionApplied | double |  | La tasa de comisión aplicada a los valores de P&L. Solo se devuelve si se solicita la opción netOfCommision |  |
|  | profitAndLosses | Lista<RunnerProfitAndLoss> |  | Calcula los datos de ganancias y pérdidas. |  |
|  |  |  |  |  |  |
| RunnerProfitAndLoss | RunnerProfitAndLoss | RunnerProfitAndLoss | RunnerProfitAndLoss | RunnerProfitAndLoss | RunnerProfitAndLoss |
| --- | --- | --- | --- | --- | --- |
|  | Ganancias y pérdidas si la selección gana o pierde | Ganancias y pérdidas si la selección gana o pierde | Ganancias y pérdidas si la selección gana o pierde | Ganancias y pérdidas si la selección gana o pierde |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | selectionId | SelectionId |  | El identificador único para la selección |  |
|  | ifWin | double |  | Las ganancias o pérdidas para el mercado si esta selección es la ganadora. |  |
|  | ifLose | double |  | Las ganancias o pérdidas para el mercado si esta selección es la perdedora. Solo se devuelve para los mercados de probabilidades de varios ganadores. |  |
|  | ifPlace | double |  | Las ganancias o pérdidas para el mercado si se hace esta selección. Se aplica a marketType EACH_WAY solamente. |  |
|  |  |  |  |  |  |
| Alias de tipo | Alias de tipo | Alias de tipo | Alias de tipo | Alias de tipo |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |
|  | Alias | Tipo |  |  |
|  | MarketType | Cadena |  |  |
|  | Venue | Cadena |  |  |
|  | MarketId | Cadena |  |  |
|  | SelectionId | long |  |  |
|  | Hándicap | double |  |  |
|  | EventId | Cadena |  |  |
|  | EventTypeId | Cadena |  |  |
|  | CountryCode | Cadena |  |  |
|  | ExchangeId | Cadena |  |  |
|  | CompetitionId | Cadena |  |  |
|  | Price | double |  |  |
|  | Size | double |  |  |
|  | BetId | Cadena |  |  |
|  | MatchId | Cadena |  |  |
|  | CustomerOrderRef | Cadena |  |  |
|  | CustomerStrategyRef | Cadena |  |  |
|  |  |  |  |  |
| Interfaz | Extremo | Prefijo de JSON-RPC | Ejemplo de <methodname> |
| --- | --- | --- | --- |
| JSON-RPC | https://api.betfair.com/exchange/account/json-rpc/v1 | <methodname> | AccountAPING/v1.0/getAccountFunds |
| JSON REST | https://api.betfair.com/exchange/account/rest/v1.0/ |  | getAccountFunds/ |
| Tipo | Operación | Descripción | Disponible solo para los proveedores de software | X-Authentication | X-Applicaiton |
| --- | --- | --- | --- | --- | --- |
| DeveloperApp | createDeveloperAppKeys (String appName ) | Cree 2 claves de aplicación para el usuario dado, una ‘retardada’ y otra ‘en directo’. Debe presentar una solicitud para activar su clave de aplicación ‘en directo’. |  | Obligatorio |  |
| Lista< DeveloperApp > | getDeveloperAppKeys ( ) | Obtenga todas las claves de aplicaciones que posee el desarrollador/proveedor determinado |  | Obligatorio |  |
| AccountFundsResponse | getAccountFunds ( ) | Obtenga la disponibilidad para apostar el importe. |  | Obligatorio | Obligatorio |
| TransferResponse | transferFunds (Wallet de, Wallet a, importe doble) |  |  | Obligatorio | Obligatorio |
| AccountDetailsResponse | getAccountDetails ( ) | Devuelve los detalles relacionados con su cuenta, incluida su tasa de descuento y saldo de puntos de Betfair. |  | Obligatorio | Obligatorio |
| String | getVendorClientId ( ) | Devuelve el ID de cliente de proveedor para la cuenta de cliente, que es un identificador único para ese cliente. |  | Obligatorio | Obligatorio |
| String | getApplicationSubscriptionToken 
( intsubscriptionLength ) | Se utilizan para crear nuevos tokens de suscripción para una solicitud. Devuelve el token de suscripción recién generado que se puede proporcionar al usuario final. Disponible únicamente para las claves de aplicación administradas por el propietario (proveedor) | S | Obligatorio | Obligatorio |
| Status | activateApplicationSubscription 
( StringsubscriptionToken ) | Activa el token de suscripción de los clientes para una aplicación |  | Obligatorio |  |
| Status | cancelApplicationSubscription 
( StringsubscriptionToken ) | Cancela el token de suscripción. La suscripción de los clientes dejarán de estar activas una vez cancelada. Disponible únicamente para las claves de aplicación administradas por el propietario (proveedor) | S | Obligatorio | Obligatorio |
| String | updateApplicationSubscription 
( String vendorClientId, int subscriptionLength ) | Actualice una suscripción de aplicación con una nueva fecha de caducidad. Disponible únicamente para las claves de aplicación administradas por el propietario (proveedor) | S | Obligatorio | Obligatorio |
| Lista< ApplicationSubscription > | listApplicationSubscriptionTokens 
( SubscriptionStatus subscriptionStatus ) | Devuelve una lista de tokens de suscripción para una aplicación basada en el estado de suscripción que se pasó en la solicitud. | S | Obligatorio | Obligatorio |
| Lista< AccountSubscription > | listAccountSubscriptionTokens 
( ) | Lista de tokens de suscripción asociada con la cuenta. Disponible únicamente para las claves de aplicación administradas por el propietario (proveedor) | S | Obligatorio | Obligatorio |
| Lista<SubscriptionHistory> | getApplicationSubscriptionHistory 
( String vendorClientId ) | Devuelve una lista de tokens de suscripción que se han asociado con la cuenta del cliente. Disponible únicamente para las claves de aplicación administradas por el propietario (proveedor) | S | Obligatorio | Se requiere en el encabezado de la solicitud O el cuerpo de la solicitud |
| AccountStatementReport | getAccountStatement ( String locale, int fromRecord, int recordCount, Tim eRange itemDateRange, IncludeItem includeItem,Walletwallet ) | Obtenga el estado de cuenta: proporciona un registro de auditoría completo del movimiento de dinero hacia y desde su cuenta. | No está disponible mediante la Vendor Web API | Obligatorio | Obligatorio |
| Lista<CurrencyRate> | listCurrencyRates ( String fromCurrency ) | Devuelve una lista de los tipos de cambio basada en determinada moneda. |  |  |  |
| VendorAccessTokenInfo | token ( String client_id, GrantType grant_type, String code, String client_secret, String refresh_token ) | Genere una sesión de proveedor web basada en una sesión estándar identificable por el código de autenticación, la clave de aplicación y secreta del proveedor | S | Obligatorio | Obligatorio |
| VendorDetails | getVendorDetails ( String vendorId ) | Devuelve detalles acerca de un proveedor de su identificador. La respuesta incluye el nombre del proveedor y la dirección URL |  |  |  |
| Status | revokeAccessToWebApp ( long vendorId ) | Elimine el vínculo entre una cuenta y una aplicación web de proveedor Esto eliminará el refreshToken para esta suscripción de par de usuario-proveedor. |  |  |  |
| Lista<VendorDetails> | listAuthorizedWebApps ( ) | Recupere todas las aplicaciones de proveedores actualmente suscritas por el usuario que realiza la solicitud |  |  |  |
| boolean | isAccountSubscribedToWebApp ( String vendorId ) | Devuelve si una cuenta ha autorizado a una aplicación web. |  |  |  |
| Lista<AffiliateRelation> | getAffiliateRelation 
( List<String> vendorClientIds ) | Devuelve la relación entre una lista de usuarios y un afiliado | S | Obligatorio | Obligatorio |
| createDeveloperAppKeys | createDeveloperAppKeys | createDeveloperAppKeys | createDeveloperAppKeys | createDeveloperAppKeys | createDeveloperAppKeys | createDeveloperAppKeys | createDeveloperAppKeys | createDeveloperAppKeys |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | DeveloperApp createDeveloperAppKeys (String appName) muestra AccountAPINGException

Cree 2 claves de aplicación para el usuario dado, una ‘retardada’ y otra ‘en directo’. Debe presentar una solicitud para activar su clave de aplicación ‘en directo’. | DeveloperApp createDeveloperAppKeys (String appName) muestra AccountAPINGException

Cree 2 claves de aplicación para el usuario dado, una ‘retardada’ y otra ‘en directo’. Debe presentar una solicitud para activar su clave de aplicación ‘en directo’. | DeveloperApp createDeveloperAppKeys (String appName) muestra AccountAPINGException

Cree 2 claves de aplicación para el usuario dado, una ‘retardada’ y otra ‘en directo’. Debe presentar una solicitud para activar su clave de aplicación ‘en directo’. | DeveloperApp createDeveloperAppKeys (String appName) muestra AccountAPINGException

Cree 2 claves de aplicación para el usuario dado, una ‘retardada’ y otra ‘en directo’. Debe presentar una solicitud para activar su clave de aplicación ‘en directo’. | DeveloperApp createDeveloperAppKeys (String appName) muestra AccountAPINGException

Cree 2 claves de aplicación para el usuario dado, una ‘retardada’ y otra ‘en directo’. Debe presentar una solicitud para activar su clave de aplicación ‘en directo’. | DeveloperApp createDeveloperAppKeys (String appName) muestra AccountAPINGException

Cree 2 claves de aplicación para el usuario dado, una ‘retardada’ y otra ‘en directo’. Debe presentar una solicitud para activar su clave de aplicación ‘en directo’. | DeveloperApp createDeveloperAppKeys (String appName) muestra AccountAPINGException

Cree 2 claves de aplicación para el usuario dado, una ‘retardada’ y otra ‘en directo’. Debe presentar una solicitud para activar su clave de aplicación ‘en directo’. |  |
|  | Nombre de parámetro | Tipo | Obligatorio | Obligatorio | Descripción | Descripción | Descripción |  |
|  | appName | Cadena |  |  | Un nombre para mostrar para la aplicación. | Un nombre para mostrar para la aplicación. | Un nombre para mostrar para la aplicación. |  |
|  |  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Descripción | Descripción | Descripción | Descripción | Descripción |  |  |
|  | DeveloperApp | Un mapa de claves de aplicación, una marcada como ACTIVA y la otra como RETARDADA | Un mapa de claves de aplicación, una marcada como ACTIVA y la otra como RETARDADA | Un mapa de claves de aplicación, una marcada como ACTIVA y la otra como RETARDADA | Un mapa de claves de aplicación, una marcada como ACTIVA y la otra como RETARDADA | Un mapa de claves de aplicación, una marcada como ACTIVA y la otra como RETARDADA |  |  |
|  |  |  |  |  |  |  |  |  |
|  | Muestra | Muestra | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | AccountAPINGException | AccountAPINGException | AccountAPINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| getAccountDetails | getAccountDetails | getAccountDetails | getAccountDetails | getAccountDetails | getAccountDetails | getAccountDetails |
| --- | --- | --- | --- | --- | --- | --- |
|  | AccountDetailsResponse getAccountDetails  ( )  muestra AccountAPINGException

Devuelve los detalles relacionados con su cuenta, incluida su tasa de descuento y saldo de puntos de Betfair. | AccountDetailsResponse getAccountDetails  ( )  muestra AccountAPINGException

Devuelve los detalles relacionados con su cuenta, incluida su tasa de descuento y saldo de puntos de Betfair. | AccountDetailsResponse getAccountDetails  ( )  muestra AccountAPINGException

Devuelve los detalles relacionados con su cuenta, incluida su tasa de descuento y saldo de puntos de Betfair. | AccountDetailsResponse getAccountDetails  ( )  muestra AccountAPINGException

Devuelve los detalles relacionados con su cuenta, incluida su tasa de descuento y saldo de puntos de Betfair. | AccountDetailsResponse getAccountDetails  ( )  muestra AccountAPINGException

Devuelve los detalles relacionados con su cuenta, incluida su tasa de descuento y saldo de puntos de Betfair. |  |
|  | Tipo de retorno | Descripción | Descripción | Descripción |  |  |
|  | AccountDetailsResponse | Respuesta para recuperar los detalles de cuenta. | Respuesta para recuperar los detalles de cuenta. | Respuesta para recuperar los detalles de cuenta. |  |  |
|  |  |  |  |  |  |  |
|  | Muestra | Muestra | Descripción | Descripción | Descripción |  |
|  | AccountAPINGException | AccountAPINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| getAccountFunds | getAccountFunds | getAccountFunds | getAccountFunds | getAccountFunds | getAccountFunds | getAccountFunds | getAccountFunds | getAccountFunds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | AccountFundsResponse getAccountFunds ( ) muestra AccountAPINGException

Obtenga la disponibilidad para apostar el importe. El servicio getAccounts devolverá el saldo de la billetera del Reino Unido de manera predeterminada desde el extremo de API de las cuentas del Reino Unido o Australia si no se especifica el parámetro de la billetera. | AccountFundsResponse getAccountFunds ( ) muestra AccountAPINGException

Obtenga la disponibilidad para apostar el importe. El servicio getAccounts devolverá el saldo de la billetera del Reino Unido de manera predeterminada desde el extremo de API de las cuentas del Reino Unido o Australia si no se especifica el parámetro de la billetera. | AccountFundsResponse getAccountFunds ( ) muestra AccountAPINGException

Obtenga la disponibilidad para apostar el importe. El servicio getAccounts devolverá el saldo de la billetera del Reino Unido de manera predeterminada desde el extremo de API de las cuentas del Reino Unido o Australia si no se especifica el parámetro de la billetera. | AccountFundsResponse getAccountFunds ( ) muestra AccountAPINGException

Obtenga la disponibilidad para apostar el importe. El servicio getAccounts devolverá el saldo de la billetera del Reino Unido de manera predeterminada desde el extremo de API de las cuentas del Reino Unido o Australia si no se especifica el parámetro de la billetera. | AccountFundsResponse getAccountFunds ( ) muestra AccountAPINGException

Obtenga la disponibilidad para apostar el importe. El servicio getAccounts devolverá el saldo de la billetera del Reino Unido de manera predeterminada desde el extremo de API de las cuentas del Reino Unido o Australia si no se especifica el parámetro de la billetera. | AccountFundsResponse getAccountFunds ( ) muestra AccountAPINGException

Obtenga la disponibilidad para apostar el importe. El servicio getAccounts devolverá el saldo de la billetera del Reino Unido de manera predeterminada desde el extremo de API de las cuentas del Reino Unido o Australia si no se especifica el parámetro de la billetera. | AccountFundsResponse getAccountFunds ( ) muestra AccountAPINGException

Obtenga la disponibilidad para apostar el importe. El servicio getAccounts devolverá el saldo de la billetera del Reino Unido de manera predeterminada desde el extremo de API de las cuentas del Reino Unido o Australia si no se especifica el parámetro de la billetera. |  |
|  | Nombre de parámetro | Tipo | Obligatorio | Obligatorio | Descripción | Descripción | Descripción |  |
|  | wallet | Wallet |  |  | Nombre de la billetera en cuestión. Tenga en cuenta lo siguiente: Para devolver el saldo de la billetera de Exchange (Intercambio) de Australia debe especificar AUSTRALIAN como el parámetro de la billetera. | Nombre de la billetera en cuestión. Tenga en cuenta lo siguiente: Para devolver el saldo de la billetera de Exchange (Intercambio) de Australia debe especificar AUSTRALIAN como el parámetro de la billetera. | Nombre de la billetera en cuestión. Tenga en cuenta lo siguiente: Para devolver el saldo de la billetera de Exchange (Intercambio) de Australia debe especificar AUSTRALIAN como el parámetro de la billetera. |  |
|  |  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Tipo de retorno | Descripción | Descripción | Descripción |  |  |
|  | AccountFundsResponse | AccountFundsResponse | AccountFundsResponse | Respuesta para recuperar lo disponible para apostar. | Respuesta para recuperar lo disponible para apostar. | Respuesta para recuperar lo disponible para apostar. |  |  |
|  |  |  |  |  |  |  |  |  |
|  | Muestra | Muestra | Muestra | Descripción | Descripción | Descripción | Descripción |  |
|  | AccountAPINGException | AccountAPINGException | AccountAPINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| getDeveloperAppKeys | getDeveloperAppKeys | getDeveloperAppKeys | getDeveloperAppKeys | getDeveloperAppKeys | getDeveloperAppKeys | getDeveloperAppKeys |
| --- | --- | --- | --- | --- | --- | --- |
|  | Lista< DeveloperApp > getDeveloperAppKeys ( ) muestra AccountAPINGException

Obtenga todas las claves de aplicaciones que posee el desarrollador/proveedor determinado | Lista< DeveloperApp > getDeveloperAppKeys ( ) muestra AccountAPINGException

Obtenga todas las claves de aplicaciones que posee el desarrollador/proveedor determinado | Lista< DeveloperApp > getDeveloperAppKeys ( ) muestra AccountAPINGException

Obtenga todas las claves de aplicaciones que posee el desarrollador/proveedor determinado | Lista< DeveloperApp > getDeveloperAppKeys ( ) muestra AccountAPINGException

Obtenga todas las claves de aplicaciones que posee el desarrollador/proveedor determinado | Lista< DeveloperApp > getDeveloperAppKeys ( ) muestra AccountAPINGException

Obtenga todas las claves de aplicaciones que posee el desarrollador/proveedor determinado |  |
|  | Tipo de retorno | Descripción | Descripción | Descripción |  |  |
|  | Lista< DeveloperApp > | Una lista de las claves de aplicaciones que posee el desarrollador/proveedor determinado | Una lista de las claves de aplicaciones que posee el desarrollador/proveedor determinado | Una lista de las claves de aplicaciones que posee el desarrollador/proveedor determinado |  |  |
|  |  |  |  |  |  |  |
|  | Muestra | Muestra | Descripción | Descripción | Descripción |  |
|  | AccountAPINGException | AccountAPINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| getAccountStatement | getAccountStatement | getAccountStatement | getAccountStatement | getAccountStatement | getAccountStatement | getAccountStatement | getAccountStatement | getAccountStatement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | AccountStatementReport getAccountStatement ( String locale, int fromRecord, int recordCount, TimeRange itemDateRange, In cludeItem includeItem, Wallet wallet) muestra AccountAPINGException

Obtenga estado de cuenta | AccountStatementReport getAccountStatement ( String locale, int fromRecord, int recordCount, TimeRange itemDateRange, In cludeItem includeItem, Wallet wallet) muestra AccountAPINGException

Obtenga estado de cuenta | AccountStatementReport getAccountStatement ( String locale, int fromRecord, int recordCount, TimeRange itemDateRange, In cludeItem includeItem, Wallet wallet) muestra AccountAPINGException

Obtenga estado de cuenta | AccountStatementReport getAccountStatement ( String locale, int fromRecord, int recordCount, TimeRange itemDateRange, In cludeItem includeItem, Wallet wallet) muestra AccountAPINGException

Obtenga estado de cuenta | AccountStatementReport getAccountStatement ( String locale, int fromRecord, int recordCount, TimeRange itemDateRange, In cludeItem includeItem, Wallet wallet) muestra AccountAPINGException

Obtenga estado de cuenta | AccountStatementReport getAccountStatement ( String locale, int fromRecord, int recordCount, TimeRange itemDateRange, In cludeItem includeItem, Wallet wallet) muestra AccountAPINGException

Obtenga estado de cuenta | AccountStatementReport getAccountStatement ( String locale, int fromRecord, int recordCount, TimeRange itemDateRange, In cludeItem includeItem, Wallet wallet) muestra AccountAPINGException

Obtenga estado de cuenta |  |
|  | Nombre de parámetro | Tipo | Tipo | Obligatorio | Obligatorio | Descripción | Descripción |  |
|  | region | Cadena | Cadena |  |  | El idioma que se utilizará cuando sea aplicable. Si no se especifica, se devuelve el valor predeterminado de la cuenta del cliente. | El idioma que se utilizará cuando sea aplicable. Si no se especifica, se devuelve el valor predeterminado de la cuenta del cliente. |  |
|  | fromRecord | int | int |  |  | Especifica el primer registro que se devolverá. Los registros comienzan en el índice cero. Si no se especifica, el valor predeterminado será 0. | Especifica el primer registro que se devolverá. Los registros comienzan en el índice cero. Si no se especifica, el valor predeterminado será 0. |  |
|  | recordCount | int | int |  |  | Especifica el número máximo de registros que se devuelven. Tenga en cuenta que existe un límite de tamaño de página de 100. | Especifica el número máximo de registros que se devuelven. Tenga en cuenta que existe un límite de tamaño de página de 100. |  |
|  | itemDateRange | TimeRange | TimeRange |  |  | Devuelve los elementos con una itemDate dentro de este rango de fechas. Los tiempos de la fecha desde y hasta son inclusivos. Si no se especifica “desde”, los elementos más antiguos disponibles estarán en el rango. Si no se especifica “hasta”, los últimos elementos estarán en rango. Actualmente, este itemDataRange se aplica solo cuando el elemento incluido se establece en TODOS o no se especifica, los otros elementos NO están incluidos por itemDate. | Devuelve los elementos con una itemDate dentro de este rango de fechas. Los tiempos de la fecha desde y hasta son inclusivos. Si no se especifica “desde”, los elementos más antiguos disponibles estarán en el rango. Si no se especifica “hasta”, los últimos elementos estarán en rango. Actualmente, este itemDataRange se aplica solo cuando el elemento incluido se establece en TODOS o no se especifica, los otros elementos NO están incluidos por itemDate. |  |
|  | includeItem | IncludeItem | IncludeItem |  |  | Los elementos que se deben a incluir, si no se especifican, el valor predeterminado en TODOS. | Los elementos que se deben a incluir, si no se especifican, el valor predeterminado en TODOS. |  |
|  | wallet | Wallet | Wallet |  |  | Para qué billetera se devuelve statementItems. Si no especifica, entonces se selecciona la billetera del Reino Unido | Para qué billetera se devuelve statementItems. Si no especifica, entonces se selecciona la billetera del Reino Unido |  |
|  |  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción | Descripción | Descripción | Descripción |  |
|  | AccountStatementReport | AccountStatementReport | Lista de elementos de declaración ordenados cronológicamente más moreAvailable boolean para facilitar la paginación | Lista de elementos de declaración ordenados cronológicamente más moreAvailable boolean para facilitar la paginación | Lista de elementos de declaración ordenados cronológicamente más moreAvailable boolean para facilitar la paginación | Lista de elementos de declaración ordenados cronológicamente más moreAvailable boolean para facilitar la paginación | Lista de elementos de declaración ordenados cronológicamente más moreAvailable boolean para facilitar la paginación |  |
|  |  |  |  |  |  |  |  |  |
|  | Muestra | Muestra | Descripción | Descripción | Descripción | Descripción | Descripción |  |
|  | AccountAPINGException | AccountAPINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| listCurrencyRates | listCurrencyRates | listCurrencyRates | listCurrencyRates | listCurrencyRates | listCurrencyRates | listCurrencyRates | listCurrencyRates |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  | Lista<CurrencyRate> listCurrencyRates (String fromCurrency) muestra AccountAPINGException

Devuelve una lista de los tipos de cambio basada en determinada moneda. Tenga en cuenta lo siguiente: Los tipos de cambio se actualizan una vez por hora unos segundos después de la hora. | Lista<CurrencyRate> listCurrencyRates (String fromCurrency) muestra AccountAPINGException

Devuelve una lista de los tipos de cambio basada en determinada moneda. Tenga en cuenta lo siguiente: Los tipos de cambio se actualizan una vez por hora unos segundos después de la hora. | Lista<CurrencyRate> listCurrencyRates (String fromCurrency) muestra AccountAPINGException

Devuelve una lista de los tipos de cambio basada en determinada moneda. Tenga en cuenta lo siguiente: Los tipos de cambio se actualizan una vez por hora unos segundos después de la hora. | Lista<CurrencyRate> listCurrencyRates (String fromCurrency) muestra AccountAPINGException

Devuelve una lista de los tipos de cambio basada en determinada moneda. Tenga en cuenta lo siguiente: Los tipos de cambio se actualizan una vez por hora unos segundos después de la hora. | Lista<CurrencyRate> listCurrencyRates (String fromCurrency) muestra AccountAPINGException

Devuelve una lista de los tipos de cambio basada en determinada moneda. Tenga en cuenta lo siguiente: Los tipos de cambio se actualizan una vez por hora unos segundos después de la hora. | Lista<CurrencyRate> listCurrencyRates (String fromCurrency) muestra AccountAPINGException

Devuelve una lista de los tipos de cambio basada en determinada moneda. Tenga en cuenta lo siguiente: Los tipos de cambio se actualizan una vez por hora unos segundos después de la hora. |  |
|  | Nombre de parámetro | Tipo | Obligatorio | Obligatorio | Descripción | Descripción |  |
|  | fromCurrency | Cadena |  |  | La moneda en la que se calculan las tasas. Tenga en cuenta lo siguiente: GBP actualmente es el único soporte de moneda base | La moneda en la que se calculan las tasas. Tenga en cuenta lo siguiente: GBP actualmente es el único soporte de moneda base |  |
|  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Tipo de retorno | Descripción | Descripción |  |  |
|  | Lista<CurrencyRate> | Lista<CurrencyRate> | Lista<CurrencyRate> | Lista de tipos de cambio | Lista de tipos de cambio |  |  |
|  |  |  |  |  |  |  |  |
|  | Muestra | Muestra | Muestra | Descripción | Descripción | Descripción |  |
|  | AccountAPINGException | AccountAPINGException | AccountAPINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 | Desde: 1.0.0 |  |
| transferFunds | transferFunds | transferFunds | transferFunds | transferFunds | transferFunds | transferFunds | transferFunds | transferFunds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | TransferResponse transferFunds (Wallet from, Wallet to, double amount) muestra AccountAPINGException

Transfiera fondos entre el Exchange del Reino Unido y otras billeteras. | TransferResponse transferFunds (Wallet from, Wallet to, double amount) muestra AccountAPINGException

Transfiera fondos entre el Exchange del Reino Unido y otras billeteras. | TransferResponse transferFunds (Wallet from, Wallet to, double amount) muestra AccountAPINGException

Transfiera fondos entre el Exchange del Reino Unido y otras billeteras. | TransferResponse transferFunds (Wallet from, Wallet to, double amount) muestra AccountAPINGException

Transfiera fondos entre el Exchange del Reino Unido y otras billeteras. | TransferResponse transferFunds (Wallet from, Wallet to, double amount) muestra AccountAPINGException

Transfiera fondos entre el Exchange del Reino Unido y otras billeteras. | TransferResponse transferFunds (Wallet from, Wallet to, double amount) muestra AccountAPINGException

Transfiera fondos entre el Exchange del Reino Unido y otras billeteras. | TransferResponse transferFunds (Wallet from, Wallet to, double amount) muestra AccountAPINGException

Transfiera fondos entre el Exchange del Reino Unido y otras billeteras. |  |
|  | Esta operación actualmente es obsoleta debido a la eliminación de la billetera australiana | Esta operación actualmente es obsoleta debido a la eliminación de la billetera australiana | Esta operación actualmente es obsoleta debido a la eliminación de la billetera australiana | Esta operación actualmente es obsoleta debido a la eliminación de la billetera australiana | Esta operación actualmente es obsoleta debido a la eliminación de la billetera australiana | Esta operación actualmente es obsoleta debido a la eliminación de la billetera australiana | Esta operación actualmente es obsoleta debido a la eliminación de la billetera australiana |  |
|  |  |  |  |  |  |  |  |  |
|  | Nombre de parámetro | Tipo | Tipo | Tipo | Obligatorio | Descripción | Descripción |  |
|  | Nombre de parámetro | Tipo | Tipo | Tipo | Obligatorio | Descripción | Descripción |  |
|  | De | Wallet | Wallet | Wallet |  | Billetera de origen | Billetera de origen |  |
|  | a | Wallet | Wallet | Wallet |  | Billetera de destino | Billetera de destino |  |
|  | amount | double | double | double |  | Monto para transferir | Monto para transferir |  |
|  |  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Tipo de retorno | Descripción | Descripción | Descripción |  |  |
|  | TransferResponse | TransferResponse | TransferResponse | Respuesta para la acción de transferencia de fondos | Respuesta para la acción de transferencia de fondos | Respuesta para la acción de transferencia de fondos |  |  |
|  |  |  |  |  |  |  |  |  |
|  | Muestra | Muestra | Descripción | Descripción | Descripción | Descripción | Descripción |  |
|  | APINGException | APINGException | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. | Excepción genérica que se produce si esta operación falla por algún motivo. |  |
|  | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 |  |
| AccountAPINGException | AccountAPINGException | AccountAPINGException | AccountAPINGException | AccountAPINGException | AccountAPINGException | AccountAPINGException | AccountAPINGException |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación |  |  |
|  | Tipo de retorno | Tipo de retorno | Tipo de retorno | Descripción | Descripción | Descripción |  |
|  | INVALID_INPUT_DATA | INVALID_INPUT_DATA | INVALID_INPUT_DATA | Datos de entrada no válidos | Datos de entrada no válidos | Datos de entrada no válidos |  |
|  | INVALID_SESSION_INFORMATION | INVALID_SESSION_INFORMATION | INVALID_SESSION_INFORMATION | El token de sesión no se ha proporcionado, no es válido o ha caducado. | El token de sesión no se ha proporcionado, no es válido o ha caducado. | El token de sesión no se ha proporcionado, no es válido o ha caducado. |  |
|  | UNEXPECTED_ERROR | UNEXPECTED_ERROR | UNEXPECTED_ERROR | Se produjo un error interno inesperado éxito que impidió el procesamiento correcto de la solicitud. | Se produjo un error interno inesperado éxito que impidió el procesamiento correcto de la solicitud. | Se produjo un error interno inesperado éxito que impidió el procesamiento correcto de la solicitud. |  |
|  | INVALID_APP_KEY | INVALID_APP_KEY | INVALID_APP_KEY | La clave de la aplicación que se ha pasado no es válida o no está presente | La clave de la aplicación que se ha pasado no es válida o no está presente | La clave de la aplicación que se ha pasado no es válida o no está presente |  |
|  | SERVICE_BUSY | SERVICE_BUSY | SERVICE_BUSY | El servicio está actualmente demasiado ocupado para atender esta solicitud | El servicio está actualmente demasiado ocupado para atender esta solicitud | El servicio está actualmente demasiado ocupado para atender esta solicitud |  |
|  | TIMEOUT_ERROR | TIMEOUT_ERROR | TIMEOUT_ERROR | Se terminó el tiempo de espera de la llamada interna al servicio derivado | Se terminó el tiempo de espera de la llamada interna al servicio derivado | Se terminó el tiempo de espera de la llamada interna al servicio derivado |  |
|  | DUPLICATE_APP_NAME | DUPLICATE_APP_NAME | DUPLICATE_APP_NAME | Nombre de aplicación duplicado | Nombre de aplicación duplicado | Nombre de aplicación duplicado |  |
|  | APP_KEY_CREATION_FAILED | APP_KEY_CREATION_FAILED | APP_KEY_CREATION_FAILED | Error en la creación de la versión de clave de aplicación | Error en la creación de la versión de clave de aplicación | Error en la creación de la versión de clave de aplicación |  |
|  | APP_CREATION_FAILED | APP_CREATION_FAILED | APP_CREATION_FAILED | Error en la creación de una aplicación | Error en la creación de una aplicación | Error en la creación de una aplicación |  |
|  | NO_SESSION | NO_SESSION | NO_SESSION | No se ha proporcionado un encabezado de token de sesión (’X-Authentication’) en la solicitud | No se ha proporcionado un encabezado de token de sesión (’X-Authentication’) en la solicitud | No se ha proporcionado un encabezado de token de sesión (’X-Authentication’) en la solicitud |  |
|  | NO_APP_KEY | NO_APP_KEY | NO_APP_KEY | No se ha proporcionado un encabezado de clave de aplicación (’X-Application’) en la solicitud | No se ha proporcionado un encabezado de clave de aplicación (’X-Application’) en la solicitud | No se ha proporcionado un encabezado de clave de aplicación (’X-Application’) en la solicitud |  |
|  | SUBSCRIPTION_EXPIRED | SUBSCRIPTION_EXPIRED | SUBSCRIPTION_EXPIRED | Se requiere una clave de aplicación para esta operación | Se requiere una clave de aplicación para esta operación | Se requiere una clave de aplicación para esta operación |  |
|  | INVALID_SUBSCRIPTION_TOKEN | INVALID_SUBSCRIPTION_TOKEN | INVALID_SUBSCRIPTION_TOKEN | El token de suscripción proporcionado no existe | El token de suscripción proporcionado no existe | El token de suscripción proporcionado no existe |  |
|  | TOO_MANY_REQUESTS | TOO_MANY_REQUESTS | TOO_MANY_REQUESTS | Demasiadas solicitudes | Demasiadas solicitudes | Demasiadas solicitudes |  |
|  | INVALID_CLIENT_REF | INVALID_CLIENT_REF | INVALID_CLIENT_REF | Longitud no válida para la referencia del cliente | Longitud no válida para la referencia del cliente | Longitud no válida para la referencia del cliente |  |
|  | WALLET_TRANSFER_ERROR | WALLET_TRANSFER_ERROR | WALLET_TRANSFER_ERROR | Hubo un problema en la transferencia de fondos entre sus billeteras | Hubo un problema en la transferencia de fondos entre sus billeteras | Hubo un problema en la transferencia de fondos entre sus billeteras |  |
|  | INVALID_VENDOR_CLIENT_ID | INVALID_VENDOR_CLIENT_ID | INVALID_VENDOR_CLIENT_ID | El ID del cliente del proveedor no está suscrito a esta clave de aplicación | El ID del cliente del proveedor no está suscrito a esta clave de aplicación | El ID del cliente del proveedor no está suscrito a esta clave de aplicación |  |
|  |  |  |  |  |  |  |  |
|  | Otros parámetros | Tipo | Obligatorio | Obligatorio | Descripción | Descripción |  |
|  | errorDetails | Cadena |  |  | el seguimiento de la apuesta de error | el seguimiento de la apuesta de error |  |
|  | requestUUID | Cadena |  |  |  |  |  |
|  | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 |  |
| SubscriptionStatus | SubscriptionStatus | SubscriptionStatus | SubscriptionStatus |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | ALL | Cualquier estado de suscripción |  |
|  | ACTIVATED | Solo suscripciones activadas |  |
|  | UNACTIVATED | Solo suscripciones desactivadas |  |
|  | CANCELLED | Solo suscripciones canceladas |  |
|  | EXPIRED | Solo suscripciones caducadas |  |
|  |  |  |  |
| Status | Status | Status | Status | Status | Status | Status |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |
|  |  | Valor | Valor | Descripción |  |  |
|  |  | SUCCESS | SUCCESS | Estado de éxito |  |  |
|  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |
| ItemClass | ItemClass | ItemClass | ItemClass | ItemClass | ItemClass | ItemClass |
|  |  |  |  |  |  |  |
|  | Valor | Valor | Descripción | Descripción | Descripción |  |
|  | UNKNOWN | UNKNOWN | Elemento de la declaración no asignado a una clase específica. Todos los valores se concatenan en un único par clave/valor. La clave será ‘unknownStatementItem’ y el valor será una cadena separada por comas. | Elemento de la declaración no asignado a una clase específica. Todos los valores se concatenan en un único par clave/valor. La clave será ‘unknownStatementItem’ y el valor será una cadena separada por comas. | Elemento de la declaración no asignado a una clase específica. Todos los valores se concatenan en un único par clave/valor. La clave será ‘unknownStatementItem’ y el valor será una cadena separada por comas. |  |
|  |  |  |  |  |  |  |
| Wallet | Wallet | Wallet | Wallet |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | REINO UNIDO | La billetera de Exchange (Intercambio) del Reino Unido |  |
|  | AUSTRALIAN | La billetera de Exchange (Intercambio) australiana. ESTO AHORA ES OBSOLETO |  |
|  |  |  |  |
| IncludeItem | IncludeItem | IncludeItem | IncludeItem | IncludeItem | IncludeItem | IncludeItem | IncludeItem |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |
|  | Valor | Valor | Descripción | Descripción | Descripción |  |  |
|  | ALL | ALL | Incluye todos los elementos | Incluye todos los elementos | Incluye todos los elementos |  |  |
|  | DEPOSITS_WITHDRAWALS | DEPOSITS_WITHDRAWALS | Incluye pagos solamente. | Incluye pagos solamente. | Incluye pagos solamente. |  |  |
|  | EXCHANGE | EXCHANGE | Incluye solo las apuestas de intercambio | Incluye solo las apuestas de intercambio | Incluye solo las apuestas de intercambio |  |  |
|  | POKER_ROOM | POKER_ROOM | Incluye solo las transacciones de póquer | Incluye solo las transacciones de póquer | Incluye solo las transacciones de póquer |  |  |
|  |  |  |  |  |  |  |  |
| winLose | winLose | winLose | winLose | winLose | winLose | winLose | winLose |
|  |  |  |  |  |  |  |  |
|  | Valor | Valor | Valor | Descripción | Descripción | Descripción |  |
|  | RESULT_ERR | RESULT_ERR | RESULT_ERR | Error interno | Error interno | Error interno |  |
|  | RESULT_FIX | RESULT_FIX | RESULT_FIX | El resultado se ha actualizado después de un estado inicial, es decir, el historial de su cuenta ha cambiado para reflejar esto. | El resultado se ha actualizado después de un estado inicial, es decir, el historial de su cuenta ha cambiado para reflejar esto. | El resultado se ha actualizado después de un estado inicial, es decir, el historial de su cuenta ha cambiado para reflejar esto. |  |
|  | RESULT_LOST | RESULT_LOST | RESULT_LOST | Pérdida | Pérdida | Pérdida |  |
|  | RESULT_NOT_APPLICABLE | RESULT_NOT_APPLICABLE | RESULT_NOT_APPLICABLE | Incluye solo las transacciones de póquer | Incluye solo las transacciones de póquer | Incluye solo las transacciones de póquer |  |
|  | RESULT_WON | RESULT_WON | RESULT_WON | Ganó | Ganó | Ganó |  |
|  | COMMISSION_REVERSAL | COMMISSION_REVERSAL | COMMISSION_REVERSAL | Betfair ha restaurado los fondos a su cuenta que había recibido de parte suya en comisión. | Betfair ha restaurado los fondos a su cuenta que había recibido de parte suya en comisión. | Betfair ha restaurado los fondos a su cuenta que había recibido de parte suya en comisión. |  |
|  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |
| GranType | GranType | GranType | GranType | GranType | GranType | GranType | GranType |
|  |  |  |  |  |  |  |  |
|  | Valor | Descripción | Descripción | Descripción |  |  |  |
|  | AUTHORISATION_CODE |  |  |  |  |  |  |
|  | REFRESH_TOKEN |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |
| TokenType | TokenType | TokenType | TokenType |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | BEARER |  |  |
|  |  |  |  |
| AffiliateRelationStatus | AffiliateRelationStatus | AffiliateRelationStatus | AffiliateRelationStatus |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | INVALID_USER | El ID de cliente de proveedor proporcionado no es válido |  |
|  | AFFILIATED | El ID de cliente de proveedor es válido y está afiliado |  |
|  | NOT_AFFILIATED | El ID de cliente de proveedor es válido, pero no está afiliado |  |
|  |  |  |  |
| TransferResponse | TransferResponse | TransferResponse | TransferResponse | TransferResponse | TransferResponse |
| --- | --- | --- | --- | --- | --- |
|  | Respuesta de la operación de transferencia | Respuesta de la operación de transferencia | Respuesta de la operación de transferencia | Respuesta de la operación de transferencia |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | transactionId | Cadena |  | El ID de la transacción de transferencia que se utilizará en el seguimiento de las transferencias entre las billeteras |  |
|  |  |  |  |  |  |
| ApplicationSubscription | ApplicationSubscription | ApplicationSubscription | ApplicationSubscription | ApplicationSubscription | ApplicationSubscription |
| --- | --- | --- | --- | --- | --- |
|  | Detalles de la suscripción de la aplicación. | Detalles de la suscripción de la aplicación. | Detalles de la suscripción de la aplicación. | Detalles de la suscripción de la aplicación. |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | subscriptionToken | Cadena |  | Identificador de clave de aplicación |  |
|  | expiryDateTime | Fecha |  | Fecha de caducidad de la suscripción |  |
|  | expiredDateTime | Fecha |  | Fecha de caducidad de la suscripción |  |
|  | createdDateTime | Fecha |  | Fecha de creación de la suscripción |  |
|  | activationDateTime | Fecha |  | Fecha de activación de la suscripción |  |
|  | cancellationDateTime | Fecha |  | Fecha de cancelación de la suscripción |  |
|  | subscriptionStatus | SubscriptionStatus |  | Estado de la suscripción |  |
|  | clientReference | Cadena |  | Referencia del cliente |  |
|  | vendorClientId | Cadena |  | ID de cliente de proveedor |  |
|  |  |  |  |  |  |
| Historial de suscripciones | Historial de suscripciones | Historial de suscripciones | Historial de suscripciones | Historial de suscripciones | Historial de suscripciones | Historial de suscripciones | Historial de suscripciones | Historial de suscripciones | Historial de suscripciones | Historial de suscripciones |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | Detalles del historial de suscripción de la aplicación. | Detalles del historial de suscripción de la aplicación. | Detalles del historial de suscripción de la aplicación. | Detalles del historial de suscripción de la aplicación. | Detalles del historial de suscripción de la aplicación. | Detalles del historial de suscripción de la aplicación. | Detalles del historial de suscripción de la aplicación. |  |  |  |
|  | Nombre de campo | Nombre de campo | Tipo | Obligatorio | Obligatorio | Descripción | Descripción |  |  |  |
|  | subscriptionToken | subscriptionToken | Cadena |  |  | Identificador de clave de aplicación | Identificador de clave de aplicación |  |  |  |
|  | expiryDateTime | expiryDateTime | Fecha |  |  | Fecha de caducidad de la suscripción | Fecha de caducidad de la suscripción |  |  |  |
|  | expiredDateTime | expiredDateTime | Fecha |  |  | Fecha de caducidad de la suscripción | Fecha de caducidad de la suscripción |  |  |  |
|  | createdDateTime | createdDateTime | Fecha |  |  | Fecha de creación de la suscripción | Fecha de creación de la suscripción |  |  |  |
|  | activationDateTime | activationDateTime | Fecha |  |  | Fecha de activación de la suscripción | Fecha de activación de la suscripción |  |  |  |
|  | cancellationDateTime | cancellationDateTime | Fecha |  |  | Fecha de cancelación de la suscripción | Fecha de cancelación de la suscripción |  |  |  |
|  | subscriptionStatus | subscriptionStatus | SubscriptionStatus |  |  | Estado de la suscripción | Estado de la suscripción |  |  |  |
|  | clientReference | clientReference | Cadena |  |  | Referencia del cliente | Referencia del cliente |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
| AccountSubscription | AccountSubscription | AccountSubscription | AccountSubscription | AccountSubscription | AccountSubscription | AccountSubscription | AccountSubscription | AccountSubscription | AccountSubscription |
|  | Detalles de la suscripción de la aplicación. | Detalles de la suscripción de la aplicación. | Detalles de la suscripción de la aplicación. | Detalles de la suscripción de la aplicación. | Detalles de la suscripción de la aplicación. | Detalles de la suscripción de la aplicación. | Detalles de la suscripción de la aplicación. | Detalles de la suscripción de la aplicación. |  |
|  | Nombre de campo | Tipo | Tipo | Tipo | Obligatorio | Obligatorio | Descripción | Descripción |  |
|  | subscriptionTokens | Lista< SubscriptionTokenInfo > | Lista< SubscriptionTokenInfo > | Lista< SubscriptionTokenInfo > |  |  | Lista de detalles de token de suscripción | Lista de detalles de token de suscripción |  |
|  | applicationName | Cadena | Cadena | Cadena |  |  | Nombre de la aplicación | Nombre de la aplicación |  |
|  | applicationVersionId | Cadena | Cadena | Cadena |  |  | ID de versión de la aplicación | ID de versión de la aplicación |  |
|  |  |  |  |  |  |  |  |  |  |
| SubscriptionTokenInfo | SubscriptionTokenInfo | SubscriptionTokenInfo | SubscriptionTokenInfo | SubscriptionTokenInfo | SubscriptionTokenInfo |
| --- | --- | --- | --- | --- | --- |
|  | Información de token de suscripción | Información de token de suscripción | Información de token de suscripción | Información de token de suscripción |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | subscriptionToken | Cadena |  | Token de suscripción |  |
|  | activatedDateTime | Fecha |  | Fecha de activación de la suscripción |  |
|  | expiryDateTime | Fecha |  | Fecha de caducidad de la suscripción |  |
|  | expiredDateTime | Fecha |  | Fecha de caducidad de la suscripción |  |
|  | cancellationDateTime | Fecha |  | Fecha de cancelación de la suscripción |  |
|  | subscriptionStatus | SubscriptionStatus |  | Estado de la suscripción |  |
|  |  |  |  |  |  |
| DeveloperApp | DeveloperApp | DeveloperApp | DeveloperApp | DeveloperApp | DeveloperApp |
| --- | --- | --- | --- | --- | --- |
|  | Describe la aplicación específica del desarrollador/proveedor | Describe la aplicación específica del desarrollador/proveedor | Describe la aplicación específica del desarrollador/proveedor | Describe la aplicación específica del desarrollador/proveedor |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | appName | Cadena |  | El nombre exclusivo de la aplicación |  |
|  | appId | long |  | Un ID exclusivo de esta aplicación |  |
|  | appVersions | Lista< DeveloperAppVersion > |  | Las versiones de la aplicación (incluidas las claves de aplicación) |  |
|  |  |  |  |  |  |
| DeveloperAppVersion | DeveloperAppVersion | DeveloperAppVersion | DeveloperAppVersion | DeveloperAppVersion | DeveloperAppVersion |
| --- | --- | --- | --- | --- | --- |
|  | Describe una versión de una aplicación externa | Describe una versión de una aplicación externa | Describe una versión de una aplicación externa | Describe una versión de una aplicación externa |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | owner | Cadena |  | El usuario que posee la versión específica de la aplicación |  |
|  | versionId | long |  | El ID exclusivo de la aplicación |  |
|  | version | Cadena |  | La cadena de identificador de versión, como 1.0, 2.0. Exclusivo para una aplicación dada. |  |
|  | applicationKey | Cadena |  | La clave de aplicación exclusiva asociada con esta versión de la aplicación |  |
|  | delayData | boolean |  | Indica si los datos expuestos por los servicios de la plataforma como se ven mediante esta clave de aplicación están retardados o son en tiempo real. |  |
|  | subscriptionRequired | boolean |  | Indica si la versión de la aplicación necesita suscripción explícita |  |
|  | ownerManaged | boolean |  | Indica si la versión de la aplicación necesita gestión explícita por parte del propietario del software. 
Un valor de falso indica que esta es una versión destinada para el uso personal del desarrollador. |  |
|  | active | boolean |  | Indica si la versión de la aplicación está activa actualmente |  |
|  | vendorId | Cadena |  | Una cadena única pública proporcionada al proveedor que puede utilizar para pasar a la API de Betfair para identificarse. |  |
|  | vendorSecret | Cadena |  | Una cadena única privada proporcionada al proveedor que pasan con algunas llamadas para confirmar su identidad.
Vinculada con una determinada clave de aplicación. |  |
|  |  |  |  |  |  |
| AccountFundsResponse | AccountFundsResponse | AccountFundsResponse | AccountFundsResponse | AccountFundsResponse | AccountFundsResponse |
| --- | --- | --- | --- | --- | --- |
|  | Respuesta para recuperar lo disponible para apostar. | Respuesta para recuperar lo disponible para apostar. | Respuesta para recuperar lo disponible para apostar. | Respuesta para recuperar lo disponible para apostar. |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | availableToBetBalance | double |  | Cantidad disponible para apostar. |  |
|  | exposure | double |  | Exposición actual |  |
|  | retainedCommission | double |  | Importe de la comisión retenida. |  |
|  | exposureLimit | double |  | Límite de exposición. |  |
|  | discountRate | double |  | La tasa de descuento de usuario. |  |
|  | pointsBalance | int |  | El saldo de puntos de Betfair |  |
|  |  |  |  |  |  |
| AccountDetailsResponse | AccountDetailsResponse | AccountDetailsResponse | AccountDetailsResponse | AccountDetailsResponse | AccountDetailsResponse |
| --- | --- | --- | --- | --- | --- |
|  | Respuesta para los detalles de la cuenta. | Respuesta para los detalles de la cuenta. | Respuesta para los detalles de la cuenta. | Respuesta para los detalles de la cuenta. |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | currencyCode | Cadena |  | Código de moneda predeterminado del usuario. Vea Parámetros de moneda para conocer los tamaños de la apuesta mínima relacionados con cada moneda. |  |
|  | firstName | Cadena |  | Primer nombre. |  |
|  | lastName | Cadena |  | Apellido. |  |
|  | localeCode | Cadena |  | El código local. |  |
|  | region | Cadena |  | Región basada en zip/código postal de los usuarios (ISO 3166-1 Alfa-formato 3). El valor predeterminado es GBR si no se puede identificar el zip/código postal. |  |
|  | timezone | Cadena |  | Zona horaria del usuario. |  |
|  | discountRate | double |  | La tasa de descuento de usuario. |  |
|  | pointsBalance | int |  | El saldo de puntos de Betfair. |  |
|  | countryCode | Cadena |  | El país de residencia del cliente (formato ISO de 2 caracteres) |  |
|  |  |  |  |  |  |
| AccountStatementReport | AccountStatementReport | AccountStatementReport | AccountStatementReport | AccountStatementReport | AccountStatementReport |
| --- | --- | --- | --- | --- | --- |
|  | Un contenedor que representa los resultados de la búsqueda. | Un contenedor que representa los resultados de la búsqueda. | Un contenedor que representa los resultados de la búsqueda. | Un contenedor que representa los resultados de la búsqueda. |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | accountStatement | Lista<StatementItem> |  | La lista de elementos de la declaración devuelta por la consulta. |  |
|  | moreAvailable | boolean |  | Indica si hay más elementos de resultados más allá de esta página. |  |
|  |  |  |  |  |  |
| StatementItem | StatementItem | StatementItem | StatementItem | StatementItem | StatementItem |
| --- | --- | --- | --- | --- | --- |
|  | Resumen de un pedido hecho. | Resumen de un pedido hecho. | Resumen de un pedido hecho. | Resumen de un pedido hecho. |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | refId | Cadena |  | Una referencia externa, por ejemplo, equivale a betId en el caso de un elemento de declaración de apuesta de intercambio. |  |
|  | itemDate | Fecha |  | La fecha y la hora del elemento de la declaración, por ejemplo, equivalente a settledData para un elemento de la declaración de la apuesta de intercambio. (En formato ISO-8601, no traducido) |  |
|  | amount | double |  | La cantidad de dinero con la que se ajusta el saldo |  |
|  | balance | double |  | El saldo de la cuenta. |  |
|  | itemClass | ItemClass |  | Clase de elemento de declaración. Este valor determinará el conjunto de claves que se incluirá en itemClassData |  |
|  | itemClassData | Map<String,String> |  | Pares de valor de clave que describen el elemento de declaración actual. El conjunto de claves estará determinado por el itemClass |  |
|  | legacyData | StatementLegacyData |  | Conjunto de campos devuelto originalmente desde APIv6. Se proporciona para facilitar la migración desde APIv6 a API-NG, y, en última instancia, en itemClass y itemClassData |  |
|  |  |  |  |  |  |
| StatementLegacyData | StatementLegacyData | StatementLegacyData | StatementLegacyData | StatementLegacyData | StatementLegacyData | StatementLegacyData | StatementLegacyData | StatementLegacyData | StatementLegacyData |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | Resumen de un pedido hecho. | Resumen de un pedido hecho. | Resumen de un pedido hecho. | Resumen de un pedido hecho. | Resumen de un pedido hecho. | Resumen de un pedido hecho. | Resumen de un pedido hecho. | Resumen de un pedido hecho. |  |
|  | Nombre de campo | Nombre de campo | Tipo | Tipo | Tipo | Obligatorio | Descripción | Descripción |  |
|  | avgPrice | avgPrice | double | double | double |  | El precio promedio coincidente de la apuesta (nulo si no hay ninguna coincidencia) | El precio promedio coincidente de la apuesta (nulo si no hay ninguna coincidencia) |  |
|  | betSize | betSize | double | double | double |  | La cantidad de la apuesta en juego. (0 para el pago de comisiones o depósitos/retiros) | La cantidad de la apuesta en juego. (0 para el pago de comisiones o depósitos/retiros) |  |
|  | betType | betType | Cadena | Cadena | Cadena |  | A favor o en contra | A favor o en contra |  |
|  | betCategoryType | betCategoryType | Cadena | Cadena | Cadena |  | Intercambio, mercado en apuesta SP cerrada, o límite en apuesta SP cerrada. | Intercambio, mercado en apuesta SP cerrada, o límite en apuesta SP cerrada. |  |
|  | commissionRate | commissionRate | Cadena | Cadena | Cadena |  | La tasa de comisión en el mercado | La tasa de comisión en el mercado |  |
|  | eventId | eventId | long | long | long |  | Tenga en cuenta lo siguiente: este es el ID del mercado sin el exchangeId asociado | Tenga en cuenta lo siguiente: este es el ID del mercado sin el exchangeId asociado |  |
|  | eventTypeId | eventTypeId | long | long | long |  | Tipo de evento | Tipo de evento |  |
|  | fullMarketName | fullMarketName | Cadena | Cadena | Cadena |  | Nombre completo de mercado. Para los elementos de pago de tarjeta, este campo contiene el nombre de la tarjeta | Nombre completo de mercado. Para los elementos de pago de tarjeta, este campo contiene el nombre de la tarjeta |  |
|  | grossBetAmount | grossBetAmount | double | double | double |  | La cantidad ganadora a la que se le aplica la comisión. | La cantidad ganadora a la que se le aplica la comisión. |  |
|  | marketName | marketName | Cadena | Cadena | Cadena |  | Nombre de mercado. Para las transacciones de tarjeta, este campo indica el tipo de transacción de tarjeta (depósito, sin tarifa por depósito, o retiro). | Nombre de mercado. Para las transacciones de tarjeta, este campo indica el tipo de transacción de tarjeta (depósito, sin tarifa por depósito, o retiro). |  |
|  | marketType | marketType | marketType | marketType | marketType |  | Tipo de mercado. Para depósitos y retiros de la cuenta, marketType se configura en NOT_APPLICABLE. | Tipo de mercado. Para depósitos y retiros de la cuenta, marketType se configura en NOT_APPLICABLE. |  |
|  | placedDate | placedDate | Fecha | Fecha | Fecha |  | Fecha y hora de la colocación de la apuesta | Fecha y hora de la colocación de la apuesta |  |
|  | selectionId | selectionId | long | long | long |  | ID de la selección (este será el mismo para la misma selección a través de los mercados) | ID de la selección (este será el mismo para la misma selección a través de los mercados) |  |
|  | selectionName | selectionName | Cadena | Cadena | Cadena |  | Nombre de la selección | Nombre de la selección |  |
|  | startDate | startDate | Fecha | Fecha | Fecha |  | Se asentaron la fecha y la hora en la parte de la apuesta | Se asentaron la fecha y la hora en la parte de la apuesta |  |
|  | transactionType | transactionType | Cadena | Cadena | Cadena |  | Débito o crédito | Débito o crédito |  |
|  | transactionId | transactionId | long | long | long |  | El ID de referencia único asignado a depósitos y retiros de cuentas. | El ID de referencia único asignado a depósitos y retiros de cuentas. |  |
|  | winLose | winLose | winLose | winLose | winLose |  | Ganar o perder | Ganar o perder |  |
|  |  |  |  |  |  |  |  |  |  |
| TimeRange | TimeRange | TimeRange | TimeRange | TimeRange | TimeRange | TimeRange | TimeRange | TimeRange | TimeRange |
|  | TimeRange | TimeRange | TimeRange | TimeRange | TimeRange | TimeRange | TimeRange |  |  |
|  | Nombre de campo | Tipo | Tipo | Obligatorio | Descripción | Descripción | Descripción |  |  |
|  | De | Fecha | Fecha |  | desde, formato: ISO 8601 | desde, formato: ISO 8601 | desde, formato: ISO 8601 |  |  |
|  | a | Fecha | Fecha |  | hasta, formato: ISO 8601 | hasta, formato: ISO 8601 | hasta, formato: ISO 8601 |  |  |
|  |  |  |  |  |  |  |  |  |  |
| CurrencyRate | CurrencyRate | CurrencyRate | CurrencyRate | CurrencyRate | CurrencyRate |
| --- | --- | --- | --- | --- | --- |
|  | Tipo de cambio | Tipo de cambio | Tipo de cambio | Tipo de cambio |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | currencyCode | Cadena |  | Código de tres letras de ISO 4217 |  |
|  | rate | double |  | Tasa de cambio de la moneda especificada en la solicitud |  |
|  |  |  |  |  |  |
| AuthorisationResponse | AuthorisationResponse | AuthorisationResponse | AuthorisationResponse | AuthorisationResponse | AuthorisationResponse |
| --- | --- | --- | --- | --- | --- |
|  | AuthorisationResponse

Un objeto de envoltorio que contiene el código de autorización y la dirección URL de redirección para proveedores web | AuthorisationResponse

Un objeto de envoltorio que contiene el código de autorización y la dirección URL de redirección para proveedores web | AuthorisationResponse

Un objeto de envoltorio que contiene el código de autorización y la dirección URL de redirección para proveedores web | AuthorisationResponse

Un objeto de envoltorio que contiene el código de autorización y la dirección URL de redirección para proveedores web |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | authorisationCode | Cadena |  | El código de autorización |  |
|  | redirectUrl | Cadena |  | URL para redirigir al usuario a la página del proveedor |  |
|  |  |  |  |  |  |
| SubscriptionOptions | SubscriptionOptions | SubscriptionOptions | SubscriptionOptions | SubscriptionOptions | SubscriptionOptions |
| --- | --- | --- | --- | --- | --- |
|  | SubscriptionOptions

Un objeto de envoltorio que contiene los detalles de cómo se debe crear una suscripción | SubscriptionOptions

Un objeto de envoltorio que contiene los detalles de cómo se debe crear una suscripción | SubscriptionOptions

Un objeto de envoltorio que contiene los detalles de cómo se debe crear una suscripción | SubscriptionOptions

Un objeto de envoltorio que contiene los detalles de cómo se debe crear una suscripción |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | subscription_length | int |  | Por cuántos días debe durar una suscripción creada. Suscripción finalizada abierta creada si no se proporcionó el valor.
Solo es relevante si createdSubscription es verdadero. |  |
|  | subscription_token | Cadena |  | Un token de suscripción existente que el llamador desea tener activado en lugar de crear uno nuevo.
Se omite si createSubscription es verdadero. |  |
|  | client_reference | Cadena |  | Cualquier referencia de cliente para esta solicitud de token de suscripción. |  |
|  |  |  |  |  |  |
| VendorAccessTokenInfo | VendorAccessTokenInfo | VendorAccessTokenInfo | VendorAccessTokenInfo | VendorAccessTokenInfo | VendorAccessTokenInfo |
| --- | --- | --- | --- | --- | --- |
|  | Un objeto de envoltorio que contiene UserVendorSessionToken, RefreshToken y opcionalmente un token de suscripción si se creó uno | Un objeto de envoltorio que contiene UserVendorSessionToken, RefreshToken y opcionalmente un token de suscripción si se creó uno | Un objeto de envoltorio que contiene UserVendorSessionToken, RefreshToken y opcionalmente un token de suscripción si se creó uno | Un objeto de envoltorio que contiene UserVendorSessionToken, RefreshToken y opcionalmente un token de suscripción si se creó uno |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | access_token | Cadena |  | Token de sesión utilizado por proveedores web |  |
|  | token_type | TokenType |  | Tipo de token |  |
|  | expires_in | long |  | Cuánto tiempo hay hasta que caduque el token |  |
|  | refresh_token | Cadena |  | Token usado para actualizar el token de sesión en el futuro |  |
|  | application_subscription | ApplicationSubscription |  | Objeto que contiene el ID de cliente de proveedor y opcionalmente alguna información de suscripción |  |
|  |  |  |  |  |  |
| VendorDetails | VendorDetails | VendorDetails | VendorDetails | VendorDetails | VendorDetails |
| --- | --- | --- | --- | --- | --- |
|  | Un objeto de envoltorio que contiene el nombre del proveedor y la URL de redirección | Un objeto de envoltorio que contiene el nombre del proveedor y la URL de redirección | Un objeto de envoltorio que contiene el nombre del proveedor y la URL de redirección | Un objeto de envoltorio que contiene el nombre del proveedor y la URL de redirección |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | appVersionId | long |  | ID interno de la aplicación |  |
|  | vendorName | Cadena |  | Nombre del proveedor. |  |
|  | redirectUrl | Cadena |  | URL a la que se debe redirigir |  |
|  |  |  |  |  |  |
| AffiliateRelation | AffiliateRelation | AffiliateRelation | AffiliateRelation | AffiliateRelation | AffiliateRelation |
| --- | --- | --- | --- | --- | --- |
|  | Un objeto de envoltorio que contiene detalles de relación de afiliación | Un objeto de envoltorio que contiene detalles de relación de afiliación | Un objeto de envoltorio que contiene detalles de relación de afiliación | Un objeto de envoltorio que contiene detalles de relación de afiliación |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | vendorClientId | Cadena |  | ID de usuario |  |
|  | status | AffiliateRelationStatus |  | El estado de relación de afiliación |  |
|  |  |  |  |  |  |
| Interfaz | Extremo | Ejemplo <method name> |
| --- | --- | --- |
| JSON-RPC | https://api.betfair.com/exchange/heartbeat/json-rpc/v1 | HeartbeatAPING/v1.0/heartbeat |
| Interfaz | Extremo | Ejemplo <method name> |
| --- | --- | --- |
| JSON-RPC | https://api.betfair.it/exchange/heartbeat/json-rpc/v1 | HeartbeatAPING/v1.0/heartbeat |
| Interfaz | Extremo | Ejemplo <method name> |
| --- | --- | --- |
| JSON-RPC | https://api.betfair.es/exchange/heartbeat/json-rpc/v1 | HeartbeatAPING/v1.0/heartbeat |
| HeartbeatReport | Heartbeat (int prefferedTimeoutSeconds) |
| --- | --- |
| Pulso | Pulso | Pulso | Pulso | Pulso | Pulso | Pulso | Pulso | Pulso | Pulso |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | HeartbeatReport heartbeat (int preferredTimeoutSeconds) muestra APINGException
Esta operación de pulso se proporciona para ayudar a los clientes a administrar sus puestos automáticamente en el caso de que los clientes de API pierdan conectividad con la API de Betfair. Si no se recibe una solicitud de pulso en un plazo prescrito, entonces Betfair intentará cancelar todas las apuestas tipo “LÍMITE” para el cliente determinado en el intercambio específico. No hay ninguna garantía de que este servicio resulte en la cancelación de todas las apuestas, ya que hay una serie de circunstancias donde las apuestas no se pueden cancelar. Se recomienda encarecidamente la intervención manual en el caso de pérdida de conectividad para garantizar que las posiciones se administren correctamente. Si este servicio no está disponible por alguna razón, su pulso no se registrará automáticamente para evitar que las apuestas se cancelen inadvertidamente tras la reanudación del servicio. Debe administrar su posición manualmente hasta que el servicio se reanude. Es posible que también se pierdan los datos del pulso en el improbable caso de que fallen los nodos en el clúster, lo cual puede resultar en que su posición no se administre hasta que se reciba una solicitud de pulso subsiguiente. | HeartbeatReport heartbeat (int preferredTimeoutSeconds) muestra APINGException
Esta operación de pulso se proporciona para ayudar a los clientes a administrar sus puestos automáticamente en el caso de que los clientes de API pierdan conectividad con la API de Betfair. Si no se recibe una solicitud de pulso en un plazo prescrito, entonces Betfair intentará cancelar todas las apuestas tipo “LÍMITE” para el cliente determinado en el intercambio específico. No hay ninguna garantía de que este servicio resulte en la cancelación de todas las apuestas, ya que hay una serie de circunstancias donde las apuestas no se pueden cancelar. Se recomienda encarecidamente la intervención manual en el caso de pérdida de conectividad para garantizar que las posiciones se administren correctamente. Si este servicio no está disponible por alguna razón, su pulso no se registrará automáticamente para evitar que las apuestas se cancelen inadvertidamente tras la reanudación del servicio. Debe administrar su posición manualmente hasta que el servicio se reanude. Es posible que también se pierdan los datos del pulso en el improbable caso de que fallen los nodos en el clúster, lo cual puede resultar en que su posición no se administre hasta que se reciba una solicitud de pulso subsiguiente. | HeartbeatReport heartbeat (int preferredTimeoutSeconds) muestra APINGException
Esta operación de pulso se proporciona para ayudar a los clientes a administrar sus puestos automáticamente en el caso de que los clientes de API pierdan conectividad con la API de Betfair. Si no se recibe una solicitud de pulso en un plazo prescrito, entonces Betfair intentará cancelar todas las apuestas tipo “LÍMITE” para el cliente determinado en el intercambio específico. No hay ninguna garantía de que este servicio resulte en la cancelación de todas las apuestas, ya que hay una serie de circunstancias donde las apuestas no se pueden cancelar. Se recomienda encarecidamente la intervención manual en el caso de pérdida de conectividad para garantizar que las posiciones se administren correctamente. Si este servicio no está disponible por alguna razón, su pulso no se registrará automáticamente para evitar que las apuestas se cancelen inadvertidamente tras la reanudación del servicio. Debe administrar su posición manualmente hasta que el servicio se reanude. Es posible que también se pierdan los datos del pulso en el improbable caso de que fallen los nodos en el clúster, lo cual puede resultar en que su posición no se administre hasta que se reciba una solicitud de pulso subsiguiente. | HeartbeatReport heartbeat (int preferredTimeoutSeconds) muestra APINGException
Esta operación de pulso se proporciona para ayudar a los clientes a administrar sus puestos automáticamente en el caso de que los clientes de API pierdan conectividad con la API de Betfair. Si no se recibe una solicitud de pulso en un plazo prescrito, entonces Betfair intentará cancelar todas las apuestas tipo “LÍMITE” para el cliente determinado en el intercambio específico. No hay ninguna garantía de que este servicio resulte en la cancelación de todas las apuestas, ya que hay una serie de circunstancias donde las apuestas no se pueden cancelar. Se recomienda encarecidamente la intervención manual en el caso de pérdida de conectividad para garantizar que las posiciones se administren correctamente. Si este servicio no está disponible por alguna razón, su pulso no se registrará automáticamente para evitar que las apuestas se cancelen inadvertidamente tras la reanudación del servicio. Debe administrar su posición manualmente hasta que el servicio se reanude. Es posible que también se pierdan los datos del pulso en el improbable caso de que fallen los nodos en el clúster, lo cual puede resultar en que su posición no se administre hasta que se reciba una solicitud de pulso subsiguiente. | HeartbeatReport heartbeat (int preferredTimeoutSeconds) muestra APINGException
Esta operación de pulso se proporciona para ayudar a los clientes a administrar sus puestos automáticamente en el caso de que los clientes de API pierdan conectividad con la API de Betfair. Si no se recibe una solicitud de pulso en un plazo prescrito, entonces Betfair intentará cancelar todas las apuestas tipo “LÍMITE” para el cliente determinado en el intercambio específico. No hay ninguna garantía de que este servicio resulte en la cancelación de todas las apuestas, ya que hay una serie de circunstancias donde las apuestas no se pueden cancelar. Se recomienda encarecidamente la intervención manual en el caso de pérdida de conectividad para garantizar que las posiciones se administren correctamente. Si este servicio no está disponible por alguna razón, su pulso no se registrará automáticamente para evitar que las apuestas se cancelen inadvertidamente tras la reanudación del servicio. Debe administrar su posición manualmente hasta que el servicio se reanude. Es posible que también se pierdan los datos del pulso en el improbable caso de que fallen los nodos en el clúster, lo cual puede resultar en que su posición no se administre hasta que se reciba una solicitud de pulso subsiguiente. | HeartbeatReport heartbeat (int preferredTimeoutSeconds) muestra APINGException
Esta operación de pulso se proporciona para ayudar a los clientes a administrar sus puestos automáticamente en el caso de que los clientes de API pierdan conectividad con la API de Betfair. Si no se recibe una solicitud de pulso en un plazo prescrito, entonces Betfair intentará cancelar todas las apuestas tipo “LÍMITE” para el cliente determinado en el intercambio específico. No hay ninguna garantía de que este servicio resulte en la cancelación de todas las apuestas, ya que hay una serie de circunstancias donde las apuestas no se pueden cancelar. Se recomienda encarecidamente la intervención manual en el caso de pérdida de conectividad para garantizar que las posiciones se administren correctamente. Si este servicio no está disponible por alguna razón, su pulso no se registrará automáticamente para evitar que las apuestas se cancelen inadvertidamente tras la reanudación del servicio. Debe administrar su posición manualmente hasta que el servicio se reanude. Es posible que también se pierdan los datos del pulso en el improbable caso de que fallen los nodos en el clúster, lo cual puede resultar en que su posición no se administre hasta que se reciba una solicitud de pulso subsiguiente. | HeartbeatReport heartbeat (int preferredTimeoutSeconds) muestra APINGException
Esta operación de pulso se proporciona para ayudar a los clientes a administrar sus puestos automáticamente en el caso de que los clientes de API pierdan conectividad con la API de Betfair. Si no se recibe una solicitud de pulso en un plazo prescrito, entonces Betfair intentará cancelar todas las apuestas tipo “LÍMITE” para el cliente determinado en el intercambio específico. No hay ninguna garantía de que este servicio resulte en la cancelación de todas las apuestas, ya que hay una serie de circunstancias donde las apuestas no se pueden cancelar. Se recomienda encarecidamente la intervención manual en el caso de pérdida de conectividad para garantizar que las posiciones se administren correctamente. Si este servicio no está disponible por alguna razón, su pulso no se registrará automáticamente para evitar que las apuestas se cancelen inadvertidamente tras la reanudación del servicio. Debe administrar su posición manualmente hasta que el servicio se reanude. Es posible que también se pierdan los datos del pulso en el improbable caso de que fallen los nodos en el clúster, lo cual puede resultar en que su posición no se administre hasta que se reciba una solicitud de pulso subsiguiente. | HeartbeatReport heartbeat (int preferredTimeoutSeconds) muestra APINGException
Esta operación de pulso se proporciona para ayudar a los clientes a administrar sus puestos automáticamente en el caso de que los clientes de API pierdan conectividad con la API de Betfair. Si no se recibe una solicitud de pulso en un plazo prescrito, entonces Betfair intentará cancelar todas las apuestas tipo “LÍMITE” para el cliente determinado en el intercambio específico. No hay ninguna garantía de que este servicio resulte en la cancelación de todas las apuestas, ya que hay una serie de circunstancias donde las apuestas no se pueden cancelar. Se recomienda encarecidamente la intervención manual en el caso de pérdida de conectividad para garantizar que las posiciones se administren correctamente. Si este servicio no está disponible por alguna razón, su pulso no se registrará automáticamente para evitar que las apuestas se cancelen inadvertidamente tras la reanudación del servicio. Debe administrar su posición manualmente hasta que el servicio se reanude. Es posible que también se pierdan los datos del pulso en el improbable caso de que fallen los nodos en el clúster, lo cual puede resultar en que su posición no se administre hasta que se reciba una solicitud de pulso subsiguiente. |  |
|  | Nombre de parámetro | Nombre de parámetro | Nombre de parámetro | Tipo | Obligatorio | Descripción | Descripción | Descripción |  |
|  | preferredTimeoutSeconds | preferredTimeoutSeconds | preferredTimeoutSeconds | int |  | Tiempo máximo, en segundos, que puede transcurrir (sin una solicitud de pulso posterior), antes de que se envíe una solicitud de cancelación automáticamente en su nombre. El valor mínimo es 10, el valor máximo permitido es de 300. Si se especifica 0, el pulso no se registrará (o se omitirá si no tiene ningún pulso actual registrado). Todavía obtendrá un valor de actionPerformed devuelto si especifica 0, así que esto se puede usar para determinar si se realizó alguna acción desde su último pulso, sin tener que registrar realmente un nuevo pulso. Si especifica un valor negativo, se producirá el error INVALID_INPUT_DATA. Cualquier error al registrar el pulso dará como resultado el error UNEXPECTED_ERROR. Si se especifica un valor que es menor que el tiempo de espera mínimo, su pulso adoptará el mínimo tiempo de espera. Si se especifica un valor que es mayor que el tiempo de espera máximo, su pulso adoptará el máximo tiempo de espera. Los valores de tiempo de espera máximo y mínimo están sujetos a cambios, por lo que el cliente debe utilizar el actualTimeoutSeconds devuelto para establecer una frecuencia adecuada para las posteriores solicitudes de pulsos. | Tiempo máximo, en segundos, que puede transcurrir (sin una solicitud de pulso posterior), antes de que se envíe una solicitud de cancelación automáticamente en su nombre. El valor mínimo es 10, el valor máximo permitido es de 300. Si se especifica 0, el pulso no se registrará (o se omitirá si no tiene ningún pulso actual registrado). Todavía obtendrá un valor de actionPerformed devuelto si especifica 0, así que esto se puede usar para determinar si se realizó alguna acción desde su último pulso, sin tener que registrar realmente un nuevo pulso. Si especifica un valor negativo, se producirá el error INVALID_INPUT_DATA. Cualquier error al registrar el pulso dará como resultado el error UNEXPECTED_ERROR. Si se especifica un valor que es menor que el tiempo de espera mínimo, su pulso adoptará el mínimo tiempo de espera. Si se especifica un valor que es mayor que el tiempo de espera máximo, su pulso adoptará el máximo tiempo de espera. Los valores de tiempo de espera máximo y mínimo están sujetos a cambios, por lo que el cliente debe utilizar el actualTimeoutSeconds devuelto para establecer una frecuencia adecuada para las posteriores solicitudes de pulsos. | Tiempo máximo, en segundos, que puede transcurrir (sin una solicitud de pulso posterior), antes de que se envíe una solicitud de cancelación automáticamente en su nombre. El valor mínimo es 10, el valor máximo permitido es de 300. Si se especifica 0, el pulso no se registrará (o se omitirá si no tiene ningún pulso actual registrado). Todavía obtendrá un valor de actionPerformed devuelto si especifica 0, así que esto se puede usar para determinar si se realizó alguna acción desde su último pulso, sin tener que registrar realmente un nuevo pulso. Si especifica un valor negativo, se producirá el error INVALID_INPUT_DATA. Cualquier error al registrar el pulso dará como resultado el error UNEXPECTED_ERROR. Si se especifica un valor que es menor que el tiempo de espera mínimo, su pulso adoptará el mínimo tiempo de espera. Si se especifica un valor que es mayor que el tiempo de espera máximo, su pulso adoptará el máximo tiempo de espera. Los valores de tiempo de espera máximo y mínimo están sujetos a cambios, por lo que el cliente debe utilizar el actualTimeoutSeconds devuelto para establecer una frecuencia adecuada para las posteriores solicitudes de pulsos. |  |
|  |  |  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción | Descripción | Descripción | Descripción |  |  |
|  | HeartbeatReport | HeartbeatReport | Respuesta de la operación del pulso | Respuesta de la operación del pulso | Respuesta de la operación del pulso | Respuesta de la operación del pulso | Respuesta de la operación del pulso |  |  |
|  |  |  |  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción | Descripción |  |  |  |
|  | APINGException | Se muestra si la operación falla | Se muestra si la operación falla | Se muestra si la operación falla | Se muestra si la operación falla | Se muestra si la operación falla |  |  |  |
|  |  |  |  |  |  |  |  |  |  |
| HeartbeatReport | HeartbeatReport | HeartbeatReport | HeartbeatReport | HeartbeatReport | HeartbeatReport |
| --- | --- | --- | --- | --- | --- |
|  | Respuesta de la operación del pulso | Respuesta de la operación del pulso | Respuesta de la operación del pulso | Respuesta de la operación del pulso |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | actionPerformed | ActionPerformed |  | La acción realizada desde la última solicitud de pulso. |  |
|  | actualTimeoutSeconds | int |  | El tiempo de espera real aplicado a su solicitud de pulso, consulte la descripción del parámetro de solicitud de tiempo de espera para obtener más detalles. |  |
|  |  |  |  |  |  |
| ActionPerformed | ActionPerformed | ActionPerformed | ActionPerformed |
| --- | --- | --- | --- |
|  |  |  |  |
|  | Valor | Descripción |  |
|  | NONE | No se realizó ninguna acción desde el último pulso, o este es el primer pulso |  |
|  | CANCELLATION_REQUEST_SUBMITTED | Desde el último pulso, se envió una solicitud para cancelar todas las apuestas sin coincidencias |  |
|  | ALL_BETS_CANCELLED | Desde el último pulso, se cancelaron todas las apuestas sin coincidencias |  |
|  | SOME_BETS_NOT_CANCELLED | Desde el último pulso, no se cancelaron todas las apuestas sin coincidencias |  |
|  | CANCELLATION_REQUEST_ERROR | Hubo un error en la solicitud de cancelación, no se cancelaron las apuestas |  |
|  | CANCELLATION_STATUS_UNKNOWN | No hubo ninguna respuesta desde la solicitud de cancelación, el estado de la cancelación es desconocido |  |
|  |  |  |  |
| APINGException | APINGException | APINGException | APINGException | APINGException | APINGException | APINGException | APINGException | APINGException |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Tipo de retorno | Descripción | Descripción | Descripción | Descripción |  |
|  | INVALID_INPUT_DATA | INVALID_INPUT_DATA | INVALID_INPUT_DATA | Datos de entrada no válidos | Datos de entrada no válidos | Datos de entrada no válidos | Datos de entrada no válidos |  |
|  | INVALID_SESSION_INFORMATION | INVALID_SESSION_INFORMATION | INVALID_SESSION_INFORMATION | El token de sesión pasado no es válido | El token de sesión pasado no es válido | El token de sesión pasado no es válido | El token de sesión pasado no es válido |  |
|  | NO_APP_KEY | NO_APP_KEY | NO_APP_KEY | Se requiere una clave de aplicación para esta operación | Se requiere una clave de aplicación para esta operación | Se requiere una clave de aplicación para esta operación | Se requiere una clave de aplicación para esta operación |  |
|  | NO_SESSION | NO_SESSION | NO_SESSION | Se requiere un token de sesión para esta operación | Se requiere un token de sesión para esta operación | Se requiere un token de sesión para esta operación | Se requiere un token de sesión para esta operación |  |
|  | INVALID_APP_KEY | INVALID_APP_KEY | INVALID_APP_KEY | La clave de aplicación especificada no es válida | La clave de aplicación especificada no es válida | La clave de aplicación especificada no es válida | La clave de aplicación especificada no es válida |  |
|  | UNEXPECTED_ERROR | UNEXPECTED_ERROR | UNEXPECTED_ERROR | Se produjo un error interno inesperado éxito que impidió el procesamiento correcto de la solicitud. | Se produjo un error interno inesperado éxito que impidió el procesamiento correcto de la solicitud. | Se produjo un error interno inesperado éxito que impidió el procesamiento correcto de la solicitud. | Se produjo un error interno inesperado éxito que impidió el procesamiento correcto de la solicitud. |  |
|  |  |  |  |  |  |  |  |  |
|  | Otros parámetros | Tipo | Obligatorio | Obligatorio | Descripción | Descripción |  |  |
|  | errorDetails | Cadena |  |  | Detalles del error específico | Detalles del error específico |  |  |
|  | requestUUID | Cadena |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |
| Interfaz | Extremo | Prefijo de JSON-RPC | Ejemplo de <methodname> |
| --- | --- | --- | --- |
| JSON-RPC | https://api.betfair.com/exchange/scores/json-rpc/v1 | <methodname> | ScoresAPING/v1.0/listRaceDetails |
| Lista<RaceDetails> | listRaceDetails ( Set<MeetingId> meetingIds, Set<RaceId> raceIds ) |
| --- | --- |
| listRaceDetails | listRaceDetails | listRaceDetails | listRaceDetails | listRaceDetails | listRaceDetails | listRaceDetails | listRaceDetails | listRaceDetails |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | Lista<RaceDetails> listRaceDetails ( Set<MeetingId> meetingIds, Set<RaceId> raceIds) muestra APINGException

Busque las carreras para obtener sus datos. | Lista<RaceDetails> listRaceDetails ( Set<MeetingId> meetingIds, Set<RaceId> raceIds) muestra APINGException

Busque las carreras para obtener sus datos. | Lista<RaceDetails> listRaceDetails ( Set<MeetingId> meetingIds, Set<RaceId> raceIds) muestra APINGException

Busque las carreras para obtener sus datos. | Lista<RaceDetails> listRaceDetails ( Set<MeetingId> meetingIds, Set<RaceId> raceIds) muestra APINGException

Busque las carreras para obtener sus datos. | Lista<RaceDetails> listRaceDetails ( Set<MeetingId> meetingIds, Set<RaceId> raceIds) muestra APINGException

Busque las carreras para obtener sus datos. | Lista<RaceDetails> listRaceDetails ( Set<MeetingId> meetingIds, Set<RaceId> raceIds) muestra APINGException

Busque las carreras para obtener sus datos. | Lista<RaceDetails> listRaceDetails ( Set<MeetingId> meetingIds, Set<RaceId> raceIds) muestra APINGException

Busque las carreras para obtener sus datos. |  |
|  | Nombre de parámetro | Tipo | Tipo | Obligatorio | Descripción | Descripción | Descripción |  |
|  | meetingIds | Establecer<MeetingId> | Establecer<MeetingId> |  | Opcionalmente restringe los resultados a los identificadores de reunión especificados. El identificador único de la reunión equivalente a eventId para esa carrera específica, según lo devuelve listEvents. Opcionalmente restringe los resultados a los identificadores de reunión especificados. | Opcionalmente restringe los resultados a los identificadores de reunión especificados. El identificador único de la reunión equivalente a eventId para esa carrera específica, según lo devuelve listEvents. Opcionalmente restringe los resultados a los identificadores de reunión especificados. | Opcionalmente restringe los resultados a los identificadores de reunión especificados. El identificador único de la reunión equivalente a eventId para esa carrera específica, según lo devuelve listEvents. Opcionalmente restringe los resultados a los identificadores de reunión especificados. |  |
|  | raceIds | Establecer<Rac eId> | Establecer<Rac eId> |  | Opcionalmente restringe los resultados a los identificadores de carrera especificados. Identificador único de la carrera en el formato meetingid.raceTime (hhmm). raceTime está en GMT. Opcionalmente restringe los resultados a los identificadores de carrera especificados. El campo raceID se devuelve dentro del nodo de la carrera del servicio de Datos de navegación para aplicaciones. | Opcionalmente restringe los resultados a los identificadores de carrera especificados. Identificador único de la carrera en el formato meetingid.raceTime (hhmm). raceTime está en GMT. Opcionalmente restringe los resultados a los identificadores de carrera especificados. El campo raceID se devuelve dentro del nodo de la carrera del servicio de Datos de navegación para aplicaciones. | Opcionalmente restringe los resultados a los identificadores de carrera especificados. Identificador único de la carrera en el formato meetingid.raceTime (hhmm). raceTime está en GMT. Opcionalmente restringe los resultados a los identificadores de carrera especificados. El campo raceID se devuelve dentro del nodo de la carrera del servicio de Datos de navegación para aplicaciones. |  |
|  |  |  |  |  |  |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Descripción | Descripción | Descripción | Descripción |  |  |
|  | Lista<RaceDetails> | Lista<RaceDetails> | Lista de detalles de carrera recuperados | Lista de detalles de carrera recuperados | Lista de detalles de carrera recuperados | Lista de detalles de carrera recuperados |  |  |
|  |  |  |  |  |  |  |  |  |
|  | Muestra | Descripción | Descripción | Descripción | Descripción |  |  |  |
|  | APINGException |  |  |  |  |  |  |  |
|  | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 | Desde 1.0.0 |  |
| RaceDetails | RaceDetails | RaceDetails | RaceDetails | RaceDetails | RaceDetails |
| --- | --- | --- | --- | --- | --- |
|  | Detalles de la carrera | Detalles de la carrera | Detalles de la carrera | Detalles de la carrera |  |
|  | Nombre de campo | Tipo | Obligatorio | Descripción |  |
|  | meetingId | MeetingId |  | El identificador único de la reunión equivalente a eventId para esa carrera específica, según lo devuelve listEvents. Opcionalmente restringe los resultados a los identificadores de reunión especificados. |  |
|  | raceId | RaceId |  | Identificador único de la carrera en el formato meetingid.raceTime (hhmm). Opcionalmente restringe los resultados a los identificadores de carrera especificados. |  |
|  | raceStatus | RaceStatus |  | El estado actual de la carrera. |  |
|  | lastUpdated | LastUpdated |  | Este es el momento en que se actualizaron por última vez los datos |  |
|  | responseCode | ResponseCode |  |  |  |
|  |  |  |  |  |  |
| Alias | Tipo |
| --- | --- |
| UpdateSequence | long |
| EventId | Cadena |
| EventTypeId | Cadena |
| EventTime | Cadena |
| UpdateType | Cadena |
| LastUpdated | Fecha |
| MeetingId | Cadena |
| RaceId | Cadena |
| RaceStatus | RaceStatus | RaceStatus | RaceStatus | RaceStatus |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |
|  | Valor | Descripción | Descripción |  |
|  | DORMANT | No hay datos disponibles para esta carrera. | No hay datos disponibles para esta carrera. |  |
|  | DELAYED | El inicio de la carrera se ha retrasado | El inicio de la carrera se ha retrasado |  |
|  | PARADING | Los caballos/galgos están en el circuito de presentación | Los caballos/galgos están en el circuito de presentación |  |
|  | GOINGDOWN | Los caballos están yendo al punto de partida | Los caballos están yendo al punto de partida |  |
|  | GOINGBEHIND | Los caballos van detrás de los establos | Los caballos van detrás de los establos |  |
|  | APPROACHING | Los galgos se acercan los bancos | Los galgos se acercan los bancos |  |
|  | GOINGINTRAPS | Los galgos se están colocando en los bancos | Los galgos se están colocando en los bancos |  |
|  | HARERUNNING | La liebre ha comenzado | La liebre ha comenzado |  |
|  | ATTHEPOST | Los caballos están en el puesto | Los caballos están en el puesto |  |
|  | OFF | La carrera ha comenzado | La carrera ha comenzado |  |
|  | FINISHED | La carrera ha terminado | La carrera ha terminado |  |
|  | FINALRESULT | Se ha declarado el resultado (Galgos solamente) | Se ha declarado el resultado (Galgos solamente) |  |
|  | FALSESTART | Ha habido un falso comienzo | Ha habido un falso comienzo |  |
|  | PHOTOGRAPH | El resultado de la carrera está sujeto a un final de fotografía | El resultado de la carrera está sujeto a un final de fotografía |  |
|  | RESULT | Se ha anunciado el resultado de la carrera | Se ha anunciado el resultado de la carrera |  |
|  | WEIGHEDIN | Los jinetes se han pesado | Los jinetes se han pesado |  |
|  | RACEVOID | La carrera se ha declarado nula | La carrera se ha declarado nula |  |
|  | NORACE | La carrera se ha declarado como sin carrera | La carrera se ha declarado como sin carrera |  |
|  | MEETINGABANDONED | La reunión se ha abandonado | La reunión se ha abandonado |  |
|  | RERUN | La carrera se volverá a correr | La carrera se volverá a correr |  |
|  | ABANDONED | La carrera se ha abandonado | La carrera se ha abandonado |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
| ResponseCode | ResponseCode | ResponseCode | ResponseCode | ResponseCode |
|  |  |  |  |  |
|  | Valor | Valor | Descripción |  |
|  | OK | OK | Datos devueltos correctamente |  |
|  | NO_NEW_UPDATES | NO_NEW_UPDATES | No hay actualizaciones desde los pases UpdateSequence |  |
|  | NO_LIVE_DATA_AVAILABLE | NO_LIVE_DATA_AVAILABLE | Las puntuaciones de eventos ya no están disponibles o no están en el calendario |  |
|  | SERVICE_UNAVAILABLE | SERVICE_UNAVAILABLE | La fuente de datos para el tipo de evento (tenis/fútbol, etc.) no está disponible en estos momentos |  |
|  | UNEXPECTED_ERROR | UNEXPECTED_ERROR | Se ha producido un error inesperado al recuperar datos de puntuación |  |
|  | LIVE_DATA_TEMPORARILY_UNAVAILABLE | LIVE_DATA_TEMPORARILY_UNAVAILABLE | La fuente de datos en directo para este evento/partido está temporalmente no disponible, los datos podrían ser obsoletos |  |
|  |  |  |  |  |
| APINGException | APINGException | APINGException | APINGException | APINGException | APINGException | APINGException | APINGException | APINGException |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación | Esta excepción se produce cuando falla una operación |  |  |  |
|  | Tipo de retorno | Tipo de retorno | Tipo de retorno | Descripción | Descripción | Descripción | Descripción |  |
|  | UNEXPECTED_ERROR | UNEXPECTED_ERROR | UNEXPECTED_ERROR | La operación falló con un error inesperado. | La operación falló con un error inesperado. | La operación falló con un error inesperado. | La operación falló con un error inesperado. |  |
|  | INVALID_INPUT_DATA | INVALID_INPUT_DATA | INVALID_INPUT_DATA | Datos de entrada no válidos | Datos de entrada no válidos | Datos de entrada no válidos | Datos de entrada no válidos |  |
|  | INVALID_SESSION_INFORMATION | INVALID_SESSION_INFORMATION | INVALID_SESSION_INFORMATION | El token de sesión pasado no es válido o caducó | El token de sesión pasado no es válido o caducó | El token de sesión pasado no es válido o caducó | El token de sesión pasado no es válido o caducó |  |
|  | INVALID_APP_KEY | INVALID_APP_KEY | INVALID_APP_KEY | La clave de aplicación especificada no es válida | La clave de aplicación especificada no es válida | La clave de aplicación especificada no es válida | La clave de aplicación especificada no es válida |  |
|  | SERVICE_BUSY | SERVICE_BUSY | SERVICE_BUSY | El servicio está actualmente demasiado ocupado para atender esta solicitud | El servicio está actualmente demasiado ocupado para atender esta solicitud | El servicio está actualmente demasiado ocupado para atender esta solicitud | El servicio está actualmente demasiado ocupado para atender esta solicitud |  |
|  | TIMEOUT_ERROR | TIMEOUT_ERROR | TIMEOUT_ERROR | Se terminó el tiempo de espera de la llamada interna al servicio derivado | Se terminó el tiempo de espera de la llamada interna al servicio derivado | Se terminó el tiempo de espera de la llamada interna al servicio derivado | Se terminó el tiempo de espera de la llamada interna al servicio derivado |  |
|  | NO_SESSION | NO_SESSION | NO_SESSION | Se requiere un token de sesión para esta operación | Se requiere un token de sesión para esta operación | Se requiere un token de sesión para esta operación | Se requiere un token de sesión para esta operación |  |
|  | NO_APP_KEY | NO_APP_KEY | NO_APP_KEY | Se requiere una clave de aplicación para esta operación | Se requiere una clave de aplicación para esta operación | Se requiere una clave de aplicación para esta operación | Se requiere una clave de aplicación para esta operación |  |
|  | TOO_MANY_REQUESTS | TOO_MANY_REQUESTS | TOO_MANY_REQUESTS | Demasiadas solicitudes | Demasiadas solicitudes | Demasiadas solicitudes | Demasiadas solicitudes |  |
|  | SERVICE_UNAVAILABLE | SERVICE_UNAVAILABLE | SERVICE_UNAVAILABLE | El servicio no está disponible en este momento | El servicio no está disponible en este momento | El servicio no está disponible en este momento | El servicio no está disponible en este momento |  |
|  |  |  |  |  |  |  |  |  |
|  | Otros parámetros | Tipo | Obligatorio | Obligatorio | Descripción | Descripción |  |  |
|  | errorDetails | Cadena |  |  | el seguimiento de la apuesta de error | el seguimiento de la apuesta de error |  |  |
|  | requestUUID | Cadena |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |
| Precio | Incremento |
| --- | --- |
| 1,01 2 | 0,01 |
| 2 3 | 0,02 |
| 3 4 | 0,05 |
| 4 6 | 0,1 |
| 6 10 | 0,2 |
| 10 20 | 0,5 |
| 20 30 | 1 |
| 30 50 | 2 |
| 50 100 | 5 |
| 100 1000 | 10 |
| Precio | Incremento |
| --- | --- |
| 1,01 1000 | 0,01 |
| Nombre de moneda | Símbolo | Código de moneda | Tamaño de apuesta mín. | Tamaño de depósito mín. | Riesgo de BSP mín. | Pago de apuesta mínima |
| --- | --- | --- | --- | --- | --- | --- |
| Libras esterlinas | £ | GBP | 2 | 10 | 10 | 10 |
| Euro | EUR | EUR | 2 | 15 | 20 | 20 |
| Dólar estadounidense | USD | USD | 4 | 15 | 20 | 20 |
| Dólar de Hong Kong | HKD | HKD | 25 | 150 | 125 | 125 |
| Dólar australiano | AUD | AUD | 5 | 30 | 30 | 30 |
| Dólar canadiense | CAD | CAD | 6 | 25 | 30 | 30 |
| Coronas Danesas | DKK | DKK | 30 | 150 | 150 | 150 |
| Coronas noruegas | NOK | NOK | 30 | 150 | 150 | 150 |
| Corona sueca | SEK | SEK | 30 | 150 | 150 | 150 |
| Dólar de Singapur | SGD | SGD | 6 | 30 | 30 | 30 |
| Parámetro | Descripción |
| --- | --- |
| WEIGHT_UNITS | La unidad de peso utilizada. |
| ADJUSTED_RATING | Las calificaciones ajustadas son las clasificaciones específicas de una carrera que reflejan los pesos asignados en la carrera y, en algunas circunstancias, la edad del caballo. En su conjunto, representan la oportunidad que tiene cada corredor en el formulario. https://www.timeform.com/Racing/Articles/How_the_ratings_for_a_race_are_calculated Tenga en cuenta que estos datos solo se devuelven para quienes tengan una suscripción de Premium Timeform |
| DAM_YEAR_BORN | El año del nacimiento de la madre del caballo |
| DAYS_SINCE_LAST_RUN | El número de días desde la última vez que corrió el caballo |
| WEARING | Cualquier equipo adicional que use el caballo |
| DAMSIRE_YEAR_BORN | El año en el que nació el abuelo materno del caballo |
| SIRE_BRED | El país donde se crió el padre del caballo |
| TRAINER_NAME | El nombre del entrenador del caballo |
| STALL_DRAW | El número del puesto desde donde comienza el caballo |
| SEX_TYPE | El sexo del caballo |
| OWNER_NAME | El propietario del caballo |
| SIRE_NAME | El nombre del padre del caballo |
| FORECASTPRICE_NUMERATOR | El numerador del precio del pronóstico |
| FORECASTPRICE_DENOMINATOR | El denominador del precio del pronóstico |
| JOCKEY_CLAIM | La reducción en el peso que lleva el caballo para un jinete particular si corresponde. |
| WEIGHT_VALUE | El peso del caballo |
| DAM_NAME | El nombre de la madre del caballo |
| AGE | La edad del caballo |
| COLOUR_TYPE | El color del caballo |
| DAMSIRE_BRED | El país donde nació el abuelo del caballo |
| DAMSIRE_NAME | El nombre del abuelo del caballo |
| SIRE_YEAR_BORN | El año en que nació el padre del caballo |
| OFFICIAL_RATING | La clasificación oficial del caballo |
| FORM | El reciente formulario del caballo |
| BRED | El país en el que nació el caballo |
| runnerId | El runnerId para el caballo |
| JOCKEY_NAME | El nombre del jockey. Tenga en cuenta lo siguiente: Este campo contendrá la palabra ‘Reserva’ en caso de que el caballo se haya introducido en el mercado como un corredor de reserva. Cualquier corredor de reserva se retirará del mercado una vez que se haya confirmado que no correrá. |
| DAM_BRED | El país donde nació la madre del caballo |
| COLOURS_DESCRIPTION | La descripción textual de la vestimenta del jinete |
| COLOURS_FILENAME | Una dirección URL relacionada con un archivo de imagen correspondiente a la vestimenta del jinete Debe agregar el valor de este campo a la URL base: http://content-cache.betfair.com/feeds_images/Horses/SilkColours/ Note: no se proporcionan imágenes de la vestimenta para las carreras en EE. UU. Las imágenes de la tela de la silla utilizada para la carrera en EE. UU. se puede ver a través de https://sn4.cdnbf.net/exchange/plus/images/app/common/assets/images/saddlecloths-sprite_2608.gif |
| CLOTH_NUMBER | El número en la tela de la silla |
| CLOTH_NUMBER ALPHA | El número en la tela de la silla En las carreras de EE. UU., donde el corredor tiene una pareja, este campo mostrará el número en la tela de la pareja del corredor, por ejemplo "1A" |
| Ubicación | Abreviatura | Notas |
| --- | --- | --- |
| África/Johannesburgo | RSA |  |
| América/Costa_Rica | SJMT |  |
| América/Indiana/Indianápolis | IEST | Norteamérica este de Indiana |
| América/Santiago | SMT |  |
| Asia/Bangkok | THAI |  |
| Asia/Calcuta | INT |  |
| Asia/Dubái | UAE |  |
| Australia/Adelaida | ACST |  |
| Australia/Darwin | ANST |  |
| Australia/Perth | AWST |  |
| Australia/Queensland | AQST |  |
| Australia/Sídney | AEST |  |
| Brasil/Este | BRT |  |
| Brasil/Oeste | AMT |  |
| CET | CET | Hora central europea |
| EET | EET | Hora de Europa oriental |
| Etc/GMT-5 | PKT |  |
| Europa/Londres | UKT |  |
| Europa/Moscú | MSK |  |
| GMT/UTC | GMT/UTC | Hora del meridiano de Greenwich/Hora universal coordinada |
| Hong Kong | HK |  |
| Jamaica | KMT |  |
| Japón | JPT |  |
| NZ | NZT | Nueva Zelanda |
| EE. UU./Alaska | AKST |  |
| EE. UU./Arizona | AST |  |
| EE. UU./Central | CST |  |
| EE. UU./Este | EST |  |
| EE. UU./Hawái | HST |  |
| EE. UU./Montaña | MST |  |
| EE. UU./Pacífico | PST |  |
| Significado | FaultCode | Cliente/ Servidor | Código de respuesta de transporte de HTTP asociado | Comentarios |
| --- | --- | --- | --- | --- |
| DSC-0008 | JSONDeserialisationParseFailure | Cliente | 400 |  |
| DSC-0009 | ClassConversionFailure | Cliente | 400 | Formato no válido para el parámetro, por ejemplo, si se pasa una cadena donde se esperaba un número. También puede ocurrir cuando se pasa un valor que no coincide con ninguna enumeración válida. |
| DSC-0018 | MandatoryNotDefined | Cliente | 400 | Un parámetro marcado como obligatorio no fue proporcionado |
| DSC-0019 | Timeout | Servidor | 504 | Ha terminado el tiempo de espera de la solicitud |
| DSC-0021 | NoSuchOperation | Cliente | 404 | La operación especificada no existe. |
| DSC-0023 | NoSuchService | Cliente | 404 |  |
| DSC-0024 | RescriptDeserialisationFailure | Cliente | 400 | Excepción durante la deserialización de la solicitud de RESCRIPT |
| DSC-0034 | UnknownCaller | Cliente | 400 | Una clave de aplicación válida y activa no se ha proporcionado en la solicitud. Compruebe que su clave de aplicación esté activa. Consulte claves de aplicación para obtener más información sobre las claves de aplicación. |
| DSC-0035 | UnrecognisedCredentials | Cliente | 400 |  |
| DSC-0036 | InvalidCredentials | Cliente | 400 |  |
| DSC-0037 | SubscriptionRequired | Cliente | 403 | El usuario no está suscrito a la clave de aplicación proporcionada |
| DSC-0038 | OperationForbidden | Cliente | 403 | La clave de aplicación que se envía con la solicitud no tiene permitido acceder a la operación |
| Idioma | Código regional |
| --- | --- |
| Inglés | en |
| Danés | da |
| Sueco | sv |
| Alemán | de |
| Italiano | it |
| Griego | el |
| Español | es |
| Turco | tr |
| Coreano | ko |
| Checo | cs |
| Búlgaro | bg |
| Ruso | ru |
| Francés | fr |
| Thai | th |