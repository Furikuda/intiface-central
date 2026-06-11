// Client Mode URL derivation.
//
// The user enters a single server URL (e.g. `https://domain.com:8443/intiface`).
// From it we derive both:
//   - the WebSocket address the engine dials out to: `wss://domain.com:8443/intiface/ws`
//   - the shareable control URL: `https://domain.com:8443/intiface/?session=<id>`
//
// This assumes the WebSocket endpoint and the web UI live behind one host:port,
// differing only by path (a reverse-proxy deployment).

Uri? _parseServerUrl(String serverUrl) {
  final uri = Uri.tryParse(serverUrl.trim());
  if (uri == null || uri.host.isEmpty) return null;
  if (uri.scheme != "http" && uri.scheme != "https") return null;
  return uri;
}

/// Base path with any trailing slash(es) removed. `""` for root, `/intiface` otherwise.
String _basePath(Uri uri) {
  var path = uri.path;
  while (path.endsWith("/")) {
    path = path.substring(0, path.length - 1);
  }
  return path;
}

/// `https://host:port/path` -> `wss://host:port/path/ws` (http -> ws).
/// Returns "" if the input isn't a usable http(s) URL.
String deriveWebsocketAddress(String serverUrl) {
  final uri = _parseServerUrl(serverUrl);
  if (uri == null) return "";
  return Uri(
    scheme: uri.scheme == "https" ? "wss" : "ws",
    host: uri.host,
    port: uri.hasPort ? uri.port : null,
    path: "${_basePath(uri)}/ws",
  ).toString();
}

/// `https://host:port/path` -> `https://host:port/path/?session=<id>`.
/// Returns "" if the input isn't a usable http(s) URL.
String deriveControlUrl(String serverUrl, String sessionId) {
  final uri = _parseServerUrl(serverUrl);
  if (uri == null) return "";
  return Uri(
    scheme: uri.scheme,
    host: uri.host,
    port: uri.hasPort ? uri.port : null,
    path: "${_basePath(uri)}/",
    queryParameters: {"session": sessionId},
  ).toString();
}
