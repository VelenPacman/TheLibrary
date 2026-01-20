import threading
import time
import numpy as np
import tkinter as tk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import serial
import pandas as pd  # <-- AGGIUNTO per Excel [web:11][web:15]
from tkinter import filedialog  # <-- AGGIUNTO per dialogo salvataggio [web:16]
from tkinter import messagebox  # <-- AGGIUNTO per messagebox [web:17][web:20]

# ===============================
# CONFIGURAZIONE BLUETOOTH
# ===============================
BT_PORT = "COM7"
BT_BAUD = 115200

# ===============================
# VARIABILI GLOBALI
# ===============================
secondi = []
umidita = []
temperatura = []
lock = threading.Lock()
start_time = time.time()
MODALITA = None
aggiornamento_attivo = True
metriche_label = None  # Label per metriche
mostra_metriche = False  # Le metriche NON si vedono all'inizio
pulsante_stop = None  # Riferimento al pulsante STOP/PLAY
ignora_prossimo_dato = False  # Flag per ignorare il primo dato dopo PLAY
lista_dati = None  # Listbox per mostrare i dati ricevuti

# ===============================
# THREAD BLUETOOTH
# ===============================
def bluetooth_reader():
    try:
        ser = serial.Serial(BT_PORT, BT_BAUD, timeout=1)
        print("Bluetooth connesso")
    except Exception as e:
        print("Errore Bluetooth:", e)
        return

    while True:
        try:
            line = ser.readline().decode().strip()
            if not line.startswith("DATA;"):
                continue

            parts = line.split(";")
            t_val = float(parts[1].split("=")[1])
            h_val = int(parts[2].split("=")[1])

            # Aggiungi dati solo se l'aggiornamento è attivo
            if aggiornamento_attivo:
                with lock:
                    global ignora_prossimo_dato, start_time

                    # Ignora il primo dato dopo PLAY per evitare sovrapposizioni
                    if ignora_prossimo_dato:
                        ignora_prossimo_dato = False

                        # Ricalcola start_time basandosi sull'ultimo punto
                        if len(secondi) > 0:
                            ultimo_tempo = secondi[-1]
                            start_time = time.time() - ultimo_tempo
                    else:
                        # Calcola il tempo dalla partenza e aggiungi il dato
                        t = time.time() - start_time
                        secondi.append(t)
                        temperatura.append(t_val)
                        umidita.append(h_val)

                        # Aggiorna la listbox se esiste
                        if lista_dati is not None:
                            try:
                                # Aggiungi il nuovo dato in cima alla lista con formato compatto
                                lista_dati.insert(0, f"T:{t:5.1f}s|T:{t_val:5.1f}°C|U:{h_val:3d}%")
                                # Mantieni solo gli ultimi 50 elementi
                                if lista_dati.size() > 50:
                                    lista_dati.delete(50, tk.END)
                            except:
                                pass

                        if len(secondi) > 300:
                            secondi.pop(0)
                            temperatura.pop(0)
                            umidita.pop(0)
        except:
            pass

threading.Thread(target=bluetooth_reader, daemon=True).start()

# ===============================
# TKINTER BASE
# ===============================
INTERVALLO = 250
BG = "#0f0f0f"
BTN_BG = "#ffffff"
BTN_HOVER = "#dddddd"
TXT = "#ffffff"

root = tk.Tk()
root.title("ESP32 Real-Time Monitor")
root.geometry("1200x550")
root.minsize(1200, 550)  # Imposta dimensione minima
root.configure(bg=BG)

# Grid
root.rowconfigure(0, weight=0)
root.rowconfigure(1, weight=0)
root.rowconfigure(2, weight=1)
root.rowconfigure(3, weight=0)
root.rowconfigure(4, weight=0)
root.columnconfigure(0, weight=1)
root.columnconfigure(1, weight=0)  # Colonna per la lista dati

status = tk.StringVar(value="Seleziona il tipo di grafico")

# ===============================
# BOTTONE STILIZZATO
# ===============================
def fancy_button(text, command):
    b = tk.Button(
        root,
        text=text,
        font=("Segoe UI", 12, "bold"),
        bg=BTN_BG,
        fg="#000000",
        activebackground=BTN_HOVER,
        relief="flat",
        bd=0,
        width=22,
        height=2,
        command=command,
        cursor="hand2"
    )
    b.bind("<Enter>", lambda e: b.config(bg=BTN_HOVER))
    b.bind("<Leave>", lambda e: b.config(bg=BTN_BG))
    return b

# ===============================
# MENU INIZIALE
# ===============================
def mostra_menu_iniziale():
    global secondi, umidita, temperatura, aggiornamento_attivo
    aggiornamento_attivo = False
    with lock:
        secondi = []
        umidita = []
        temperatura = []

    for w in root.winfo_children():
        w.destroy()

    tk.Label(
        root,
        text="ESP32 REAL-TIME MONITOR",
        font=("Segoe UI", 18, "bold"),
        bg=BG,
        fg=TXT
    ).pack(pady=(50, 10))

    tk.Label(
        root,
        text="Seleziona il grafico da visualizzare",
        font=("Segoe UI", 11),
        bg=BG,
        fg="#bbbbbb"
    ).pack(pady=(0, 30))

    fancy_button("UMIDITÀ", lambda: avvia_grafico("umidita")).pack(pady=10)
    fancy_button("TEMPERATURA", lambda: avvia_grafico("temperatura")).pack(pady=10)
    fancy_button("UMIDITÀ + TEMPERATURA", lambda: avvia_grafico("entrambe")).pack(pady=10)

# ===============================
# CALCOLO METRICHE MANUALI
# ===============================
def calcola_metriche(y_real, y_pred):
    mse = np.mean((y_real - y_pred) ** 2)
    rmse = np.sqrt(mse)
    ss_res = np.sum((y_real - y_pred) ** 2)
    ss_tot = np.sum((y_real - np.mean(y_real)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    return mse, rmse, r2

# ===============================
# FUNZIONE TOGGLE METRICHE
# ===============================
def toggle_metriche():
    global mostra_metriche
    mostra_metriche = not mostra_metriche
    if mostra_metriche:
        metriche_label.grid()
    else:
        metriche_label.grid_remove()

# ===============================
# STOP/PLAY
# ===============================
def toggle_aggiornamento():
    global aggiornamento_attivo, start_time, ignora_prossimo_dato
    if aggiornamento_attivo:
        # Ferma
        aggiornamento_attivo = False
        status.set("Aggiornamento fermato")
        pulsante_stop.config(text="PLAY", bg="#55ff55", fg="#000000")
    else:
        # Riprendi - il prossimo dato servirà per ricalcolare start_time
        ignora_prossimo_dato = True
        aggiornamento_attivo = True
        status.set("Aggiornamento attivo")
        pulsante_stop.config(text="STOP", bg="#ff5555", fg="#ffffff")
        aggiorna_grafico()

# ===============================
# SALVA PNG + EXCEL (AGGIUNTA)
# ===============================
def salva_grafico_e_excel():
    global MODALITA, secondi, umidita, temperatura, fig

    # Permesso solo se STOP
    if aggiornamento_attivo:
        messagebox.showwarning("Attenzione", "Puoi salvare solo quando il grafico è in STOP.")
        return

    # Controllo dati
    if len(secondi) < 1:
        messagebox.showwarning("Attenzione", "Non ci sono dati da salvare.")
        return

    # Dialog per nome base file
    file_base = filedialog.asksaveasfilename(
        defaultextension="",
        filetypes=[("Tutti i file", "*.*")],
        title="Scegli nome base (senza estensione)"
    )
    if not file_base:
        return

    # 1) Salva PNG del grafico corrente
    try:
        fig.savefig(file_base + ".png", dpi=150)  # [web:11][web:13]
    except Exception as e:
        messagebox.showerror("Errore", f"Errore nel salvataggio PNG:\n{e}")
        return

    # 2) Salva dati in Excel con più tabelle
    try:
        with lock:
            t = list(secondi)
            u = list(umidita)
            temp = list(temperatura)

        writer = pd.ExcelWriter(file_base + ".xlsx", engine="xlsxwriter")  # [web:11][web:15]

        if MODALITA == "umidita":
            df_um = pd.DataFrame({
                "Tempo_s": t,
                "Umidita_%": u
            })
            df_um.to_excel(writer, sheet_name="Umidita", index=False)  # [web:14][web:18]

        elif MODALITA == "temperatura":
            df_t = pd.DataFrame({
                "Tempo_s": t,
                "Temperatura_C": temp
            })
            df_t.to_excel(writer, sheet_name="Temperatura", index=False)

        elif MODALITA == "entrambe":
            df_um = pd.DataFrame({
                "Tempo_s": t,
                "Umidita_%": u
            })
            df_t = pd.DataFrame({
                "Tempo_s": t,
                "Temperatura_C": temp
            })
            df_um.to_excel(writer, sheet_name="Umidita", index=False)
            df_t.to_excel(writer, sheet_name="Temperatura", index=False)

        writer.close()

        messagebox.showinfo(
            "Salvataggio completato",
            f"File salvati:\n{file_base}.png\n{file_base}.xlsx"
        )
    except Exception as e:
        messagebox.showerror("Errore", f"Errore nel salvataggio Excel:\n{e}")

# ===============================
# AVVIO GRAFICO
# ===============================
def avvia_grafico(mod):
    global MODALITA, aggiornamento_attivo, fig, ax, canvas, metriche_label, pulsante_stop, start_time, lista_dati

    MODALITA = mod
    aggiornamento_attivo = True
    start_time = time.time()  # Reset del tempo di partenza

    for w in root.winfo_children():
        w.destroy()

    tk.Label(
        root,
        text=f"ESP32 REAL-TIME · {MODALITA.upper()}",
        font=("Segoe UI", 16, "bold"),
        bg=BG,
        fg=TXT
    ).grid(row=0, column=0, columnspan=2, pady=(10, 5))

    tk.Label(
        root,
        textvariable=status,
        font=("Segoe UI", 10),
        bg=BG,
        fg="#aaaaaa"
    ).grid(row=1, column=0, columnspan=2, pady=5)

    frame_grafico = tk.Frame(root, bg=BG)
    frame_grafico.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

    # Frame per la lista dati sulla destra
    frame_lista = tk.Frame(root, bg=BG)
    frame_lista.grid(row=2, column=1, sticky="nsew", padx=(0, 10), pady=5)

    tk.Label(
        frame_lista,
        text="DATI RICEVUTI",
        font=("Segoe UI", 10, "bold"),
        bg=BG,
        fg=TXT
    ).pack(pady=(0, 5))

    # Scrollbar per la listbox
    scrollbar = tk.Scrollbar(frame_lista, bg=BG)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Listbox per i dati
    lista_dati = tk.Listbox(
        frame_lista,
        width=28,
        height=20,
        font=("Consolas", 9),
        bg="#1a1a1a",
        fg="#00ff88",
        selectbackground="#333333",
        yscrollcommand=scrollbar.set
    )
    lista_dati.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=lista_dati.yview)

    frame_pulsante = tk.Frame(root, bg=BG)
    frame_pulsante.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

    # Label metriche (NON visibile all'inizio)
    metriche_label = tk.Label(
        root,
        text="",
        font=("Courier", 11, "bold"),
        bg="#111111",
        fg="#00ff88",
        justify="left",
        anchor="w"
    )
    metriche_label.grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 10))
    metriche_label.grid_remove()  # Nasconde subito

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(8, 4), dpi=120)
    fig.subplots_adjust(left=0.15, right=0.95, top=0.9, bottom=0.15)

    canvas = FigureCanvasTkAgg(fig, master=frame_grafico)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    tk.Button(
        frame_pulsante,
        text="← Indietro",
        font=("Segoe UI", 12, "bold"),
        bg="#5555ff",
        fg="#ffffff",
        relief="flat",
        bd=0,
        width=12,
        height=1,
        cursor="hand2",
        command=lambda: mostra_menu_iniziale()
    ).pack(side="left", padx=(0, 10))

    # Pulsante STOP/PLAY
    pulsante_stop = tk.Button(
        frame_pulsante,
        text="STOP",
        font=("Segoe UI", 12, "bold"),
        bg="#ff5555",
        fg="#ffffff",
        relief="flat",
        bd=0,
        width=12,
        height=1,
        cursor="hand2",
        command=toggle_aggiornamento
    )
    pulsante_stop.pack(side="left", padx=(0, 10))

    # Pulsante Dettagli
    tk.Button(
        frame_pulsante,
        text="Dettagli",
        font=("Segoe UI", 12, "bold"),
        bg="#55ff55",
        fg="#000000",
        relief="flat",
        bd=0,
        width=12,
        height=1,
        cursor="hand2",
        command=toggle_metriche
    ).pack(side="left")

    # Pulsante SALVA PNG + EXCEL (AGGIUNTO)
    tk.Button(
        frame_pulsante,
        text="Salva PNG + Excel",
        font=("Segoe UI", 12, "bold"),
        bg="#ffaa00",
        fg="#000000",
        relief="flat",
        bd=0,
        width=16,
        height=1,
        cursor="hand2",
        command=salva_grafico_e_excel
    ).pack(side="left", padx=(10, 0))

    aggiorna_grafico()

# ===============================
# AGGIORNAMENTO GRAFICO
# ===============================
def aggiorna_grafico():
    if not aggiornamento_attivo:
        return

    with lock:
        if len(secondi) < 2:
            root.after(INTERVALLO, aggiorna_grafico)
            return

        X = np.array(secondi)

        if MODALITA == "umidita":
            Y = np.array(umidita)
        elif MODALITA == "temperatura":
            Y = np.array(temperatura)
        else:
            Y_um = np.array(umidita)
            Y_temp = np.array(temperatura)

        ax.clear()
        ax.grid(True, alpha=0.3)
        ax.set_xlabel("Tempo (s)", fontsize=10)
        ax.set_ylabel(
            "Umidità (%)" if MODALITA == "umidita" else
            "Temperatura (°C)" if MODALITA == "temperatura" else
            "Valore",
            fontsize=10
        )

        # Formatta gli assi per mostrare numeri normali senza troppi decimali
        from matplotlib.ticker import FormatStrFormatter
        ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
        ax.xaxis.set_major_formatter(FormatStrFormatter('%.1f'))

        if MODALITA in ["umidita", "temperatura"]:
            # Scatter dei dati reali
            ax.scatter(
                X,
                Y,
                color="cyan" if MODALITA == "umidita" else "lime",
                label="Dati"
            )

            # --- Retta di regressione ---
            coeff_ang, intercetta = np.polyfit(X, Y, 1)
            Y_pred = coeff_ang * X + intercetta
            ax.plot(X, Y_pred, "--", color="orange", label="Retta")

            # --- Parabola di regressione ---
            if len(X) >= 3:
                a, b, c = np.polyfit(X, Y, 2)
                xp = np.linspace(X.min(), X.max(), 200)
                Y_parabola = a * xp**2 + b * xp + c
                ax.plot(xp, Y_parabola, "-.", color="magenta", label="Parabola")

            # Metriche
            mse, rmse, r2 = calcola_metriche(Y, Y_pred)

            if mostra_metriche:
                testo_metriche = f"=== RETTA ===\n"
                testo_metriche += f"Equazione: y = {coeff_ang:.2f}x + {intercetta:.2f}\n"
                testo_metriche += f"MSE: {mse:.2f} RMSE: {rmse:.2f} R²: {r2:.4f}\n"

                if len(X) >= 3:
                    # Calcola metriche per la parabola
                    Y_pred_parabola = a * X**2 + b * X + c
                    mse_par, rmse_par, r2_par = calcola_metriche(Y, Y_pred_parabola)
                    testo_metriche += f"\n=== PARABOLA ===\n"
                    testo_metriche += f"Equazione: y = {a:.4f}x² + {b:.2f}x + {c:.2f}\n"
                    testo_metriche += f"MSE: {mse_par:.2f} RMSE: {rmse_par:.2f} R²: {r2_par:.4f}"

                metriche_label.config(text=testo_metriche)

            ax.legend()

        else:
            # Modalità ENTRAMBE - mostra entrambi i grafici
            ax.scatter(X, Y_um, color="cyan", label="Dati Umidità")
            ax.scatter(X, Y_temp, color="lime", label="Dati Temperatura")

            # --- Retta di regressione per UMIDITÀ ---
            coeff_ang_um, intercetta_um = np.polyfit(X, Y_um, 1)
            Y_pred_um = coeff_ang_um * X + intercetta_um
            ax.plot(X, Y_pred_um, "--", color="cyan", alpha=0.7, label="Retta Umidità")

            # --- Retta di regressione per TEMPERATURA ---
            coeff_ang_temp, intercetta_temp = np.polyfit(X, Y_temp, 1)
            Y_pred_temp = coeff_ang_temp * X + intercetta_temp
            ax.plot(X, Y_pred_temp, "--", color="lime", alpha=0.7, label="Retta Temperatura")

            # --- Parabola di regressione per UMIDITÀ ---
            if len(X) >= 3:
                a_um, b_um, c_um = np.polyfit(X, Y_um, 2)
                xp = np.linspace(X.min(), X.max(), 200)
                Y_parabola_um = a_um * xp**2 + b_um * xp + c_um
                ax.plot(
                    xp,
                    Y_parabola_um,
                    "-.",
                    color="cyan",
                    alpha=0.5,
                    label="Parabola Umidità"
                )

                # --- Parabola di regressione per TEMPERATURA ---
                a_temp, b_temp, c_temp = np.polyfit(X, Y_temp, 2)
                Y_parabola_temp = a_temp * xp**2 + b_temp * xp + c_temp
                ax.plot(
                    xp,
                    Y_parabola_temp,
                    "-.",
                    color="lime",
                    alpha=0.5,
                    label="Parabola Temperatura"
                )

            # Metriche per entrambe
            mse_um, rmse_um, r2_um = calcola_metriche(Y_um, Y_pred_um)
            mse_temp, rmse_temp, r2_temp = calcola_metriche(Y_temp, Y_pred_temp)

            if mostra_metriche:
                testo_metriche = "=== UMIDITÀ - RETTA ===\n"
                testo_metriche += f"Equazione: y = {coeff_ang_um:.2f}x + {intercetta_um:.2f}\n"
                testo_metriche += f"MSE: {mse_um:.2f} RMSE: {rmse_um:.2f} R²: {r2_um:.4f}\n"

                if len(X) >= 3:
                    Y_pred_parabola_um = a_um * X**2 + b_um * X + c_um
                    mse_par_um, rmse_par_um, r2_par_um = calcola_metriche(Y_um, Y_pred_parabola_um)
                    testo_metriche += f"\n=== UMIDITÀ - PARABOLA ===\n"
                    testo_metriche += f"Equazione: y = {a_um:.4f}x² + {b_um:.2f}x + {c_um:.2f}\n"
                    testo_metriche += f"MSE: {mse_par_um:.2f} RMSE: {rmse_par_um:.2f} R²: {r2_par_um:.4f}\n"

                testo_metriche += "\n=== TEMPERATURA - RETTA ===\n"
                testo_metriche += f"Equazione: y = {coeff_ang_temp:.2f}x + {intercetta_temp:.2f}\n"
                testo_metriche += f"MSE: {mse_temp:.2f} RMSE: {rmse_temp:.2f} R²: {r2_temp:.4f}\n"

                if len(X) >= 3:
                    Y_pred_parabola_temp = a_temp * X**2 + b_temp * X + c_temp
                    mse_par_temp, rmse_par_temp, r2_par_temp = calcola_metriche(Y_temp, Y_pred_parabola_temp)
                    testo_metriche += f"\n=== TEMPERATURA - PARABOLA ===\n"
                    testo_metriche += f"Equazione: y = {a_temp:.4f}x² + {b_temp:.2f}x + {c_temp:.2f}\n"
                    testo_metriche += f"MSE: {mse_par_temp:.2f} RMSE: {rmse_par_temp:.2f} R²: {r2_par_temp:.4f}"

                metriche_label.config(text=testo_metriche)

            ax.legend()

        ax.set_xlim(X.min(), X.max() + 0.5)
        fig.tight_layout()
        canvas.draw_idle()

        status.set(f"Punti acquisiti: {len(X)}")

    root.after(INTERVALLO, aggiorna_grafico)

# ===============================
# AVVIO APP
# ===============================
mostra_menu_iniziale()
root.mainloop()