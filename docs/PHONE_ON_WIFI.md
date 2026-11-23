# Use AniRoute on a phone over Wi-Fi

The laptop runs AniRoute, and a phone on the **same Wi-Fi** opens it in its browser. Nothing goes on the
internet except the map, place search and routing services the app already uses.

## 1. One-time setup on the laptop

Windows blocks incoming connections on networks it marks as "Public". Open **PowerShell as
administrator** (Start menu → type *PowerShell* → *Run as administrator*) and run:

```powershell
New-NetFirewallRule -DisplayName 'AniRoute web app (5173)' -Direction Inbound -Protocol TCP -LocalPort 5173 -Action Allow -Profile Any
```

## 2. Start AniRoute in phone mode

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-lan.ps1
```

The script prints the address to open, for example `https://192.168.1.127:5173`. The number can change
when you join a different network, so always use the one it prints.

Phone mode is served over **https**, because phones only allow the camera and GPS on secure pages. The
certificate is self-signed (made on this laptop), so each phone shows a warning on its first visit.

## 3. On the phone (Android or iPhone)

1. Join the **same Wi-Fi** as the laptop.
2. Open the printed `https://…:5173` address.
3. Accept the certificate warning once:
   - **Android (Chrome):** tap **Advanced**, then **Proceed to 192.168.x.x (unsafe)**.
   - **iPhone (Safari):** tap **Show Details**, then **visit this website**, and confirm.
4. Allow **camera** and **location** when the trip page asks.

Planning routes, the map, the live trip camera, GPS and the Evaluation page all work. The warning only
means the certificate wasn't issued by a public authority; the connection is still encrypted.

## If the phone can't connect

- **School or venue Wi-Fi often blocks phone-to-laptop traffic** ("client isolation"). Use a hotspot
  instead: turn on the laptop's **Mobile hotspot** (Settings → Network & internet), or the phone's
  hotspot with the laptop joined to it. The laptop still needs internet for routing.
- Make sure the firewall rule from step 1 exists, and that the script window is still open.
- On the laptop, `https://localhost:5173` should work. If it doesn't, the servers aren't running.
