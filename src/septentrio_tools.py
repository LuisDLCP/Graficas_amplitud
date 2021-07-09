from matplotlib.dates import DateFormatter, HourLocator
from matplotlib.ticker import AutoMinorLocator
import matplotlib.dates as mdates 
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import math as mt 
import datetime
import glob
import csv
import os 

class ProcessISMR():
    def __init__(self):
        self.pi = 3.14
    
    # Read ISMR files
    def read_file(self, file_path):
        """
        Input file: ISMR file (*.ismr)
        """
        self.df = pd.read_csv(file_path, header=None, squeeze=True)
        return self.df 

    # Convert GPS time: week & seconds; to UTC time.
    # OJO: It's missing the leapseconds, this value is obtain from the navigation file
    def _GPS2UTCtime(self, row):
        leapseconds = 0 # change
        gpsweek = int(row[0])
        gpsseconds = int(row[1])
        
        datetimeformat = "%Y-%m-%d %H:%M:%S"
        first_epoch = datetime.datetime.strptime("1980-01-06 00:00:00",datetimeformat)
        elapsed = datetime.timedelta(days=(gpsweek*7),seconds=(gpsseconds-leapseconds))
        
        return first_epoch + elapsed
        
    # Convert SVID to PRN
    # The PRN codes were obtained from PolaRx5S Reference Guide
    def _get_PRN(self, row):
        svid = int(row[1])
        if 1<=svid<=37:
            prn = "G"+str(svid)
        elif 38<=svid<=61:
            prn = "R"+str(svid-37)
        elif svid==62:
            prn = "NA"
        elif 63<=svid<=68:
            prn = "R"+str(svid-38)
        elif 71<=svid<=106:
            prn = "E"+str(svid-70)
        elif 107<=svid<=119:
            prn = "NA"
        elif 120<=svid<=140:
            prn = "S"+str(svid-100)
        elif 141<=svid<=177:
            prn = "C"+str(svid-140)
        elif 181<=svid<=187:
            prn = "J"+str(svid-180)
        elif 191<=svid<=197:
            prn = "I"+str(svid-190)
        elif 198<=svid<=215:
            prn = "S"+str(svid-157)
        elif 216<=svid<=222:
            prn = "I"+str(svid-208)
        else:
            prn = "svid not valid!"
        
        return prn

    # Change to UTC time and PRN
    def normalize_df(self):
        """
        Make the following changes:
        1) GPS time -> UTC time
        2) SVID -> PRN

        Output: df
        """
        # Change time
        newDate = self.df[[0,1]].apply(self._GPS2UTCtime, axis=1)    

        self.df.insert(0,column="DateTime",value=0) # create new column
        self.df["DateTime"] = newDate 

        del self.df[0]
        del self.df[1]

        # Change SVID to PRN
        self.df[2] = self.df.apply(self._get_PRN, axis=1)
        self.df.rename(columns={2:"PRN"}, inplace=True)

        # Datetime as index 
        self.df.set_index("DateTime", inplace=True)
        
        return self.df
    
    def extract_columns(self, cols): # cols: list
        """Extract ["PRN"] + certain columns.

        Input: list,  
        Output: df 
        """
        col_values = ["PRN"] + cols
        self.df = self.df[col_values] 
        return self.df

    def rename_column(self, currentColIndex, newColName):
        self.df.rename(columns={currentColIndex: newColName}, inplace=True)
        return 'Ok'
    
    def check_columnNames(self):
        """
        output: list 
        """
        return list(self.df.columns)
    
    # Identify the available constellations 
    def check_constelations(self):
        """output: list
        """
        const = self.df["PRN"].str[0].unique() # extract the first character of each cell 
        return const

    # Convert to float
    def convert2float(self, cols):
        self.df[cols] = self.df[cols].astype('float')
        return 'Ok'

    # Filter data(S4, CN0) based on the angle of the elevation 
    def filter_dataframe(self, col='CN0_sig1', on='Elev', threshold=35, new_col_name=['CN0_sig1_1', 'CN0_sig1_2']):
        """
        Filter the column 'col', based 'on' values from another column which has a certain 
        'threshold'. The new filtered 'col' is named 'new_col_name'.
        OUTPUT: df, with 2 aditional columns based on the criteria. The first column has the values 
        lower than the threshold, whereas the second column has values greater than the threshold. 
        """
        # Aux function
        def filter_col(row):
            elev = row[0]
            cn0 = row[1]   
            if elev < threshold:
                return [cn0, np.nan]
            else:
                return [np.nan, cn0]

        # Create 1 additional column with the filtered data
        df_aux = self.df[[on, col]].apply(filter_col, axis=1, result_type="expand")
        df_aux.rename(columns = {0:new_col_name[0], 1:new_col_name[1]}, inplace=True)
        self.df = pd.concat([self.df, df_aux], join='inner', axis=1)

        return 'Ok'    

    # Plot a column, for each PRN  
    def plot_fast(self, col): # col:str
        """Plot a column from a dataframe for each PRN 
        """
        #self.df.set_index("DateTime", inplace=True)
        self.df.groupby("PRN")[col].plot(style='o-')
        plt.ylabel(col)
        plt.grid(which='both')
        plt.savefig(col+".png")      
        return 'Ok'  

class ProcessSBF(ProcessISMR):
    """
    It helps to process asccii sbf streams obtained from 
    a SBF file and the tool sbf2asc.
    """
    def __init__(self):
        pass

    def read_measEpoch(self, file_path):
        """
        Read the MeasEpoch block asccii file. It contains 
        CN0 (dB-Hz) data. 
        -----
        INPUT: csv or txt file (*.txt)
        OUTPUT: df 
        """
        self.input_file_path = file_path
        # Read file
        self.df_cn = pd.read_csv(self.input_file_path, skiprows=[0,1,2,3,5], usecols=[0,1,9,11,17])
        # Rename columns 
        self.df_cn.rename(columns={"MeasType":"Signal", "CN0_dBHz [dB-Hz]":"CN0"}, inplace=True)
        #
        return self.df_cn 
    
    def read_channelStatus(self, file_path):
        """
        Read the ChannelStatus block asccii file. It contains 
        elevation(º) data. 
        -----
        INPUT: csv or txt file (*.txt)
        OUTPUT: df 
        """
        self.input_file_path = file_path
        # Read file
        self.df_elv = pd.read_csv(self.input_file_path, skiprows=[0,1,2,3,5], usecols=[0,1,2,14])
        # Rename columns 
        self.df_elv.rename(columns={"Elevation [°]":"Elev"}, inplace=True)
        #
        return self.df_elv 
    
    def _convert_freq2code(self):
        """
        Convert frequency to signal code. Review ISMR structure to 
        know the signal codes. 
        e.g. GPS_L1CA -> Sig1
        OJO: Only GPS, GALILEO & SBAS constellations are considered 
             in order to save time. Uncomment another constellation
             if you need it. 
        INPUT: df, with column "Signal" and others.
        OUTPUT: df 
        """
        def get_CN0code(signal):
            signal = signal.split("_")
            const = signal[0]
            try: 
                freq = signal[1]
            except LookupError:
                return np.nan
            #
            if const == "GPS":
                if freq == "L1CA": return "Sig1"
                elif freq == "L2C": return "Sig2"
                elif freq == "L5": return "Sig3"
                else: return np.nan
            elif const == "GAL":
                if freq == "L1BC": return "Sig1"
                elif freq == "E5a": return "Sig2"
                elif freq == "E5b": return "Sig3"
                else: return np.nan
            #elif const == "GLO":
            #    if freq == "L1CA": return "Sig1"
            #    elif freq == "L2C": return "Sig2"
            #    else: return np.nan
            #elif const == "BDS": 
            #    if freq == "B1": return "Sig1"
            #    elif freq == "B2": return "Sig2"
            #    elif freq == "B3": return "Sig3"
            #    else: return np.nan
            elif const == "GEO": # SBAS
                if freq == "L1" or freq == "L1CA": return "Sig1"
                elif freq == "L5": return "Sig2"
                else: return np.nan
            #elif const == "QZS": # const name might change, verify!
            #    if freq == "L1CA": return "Sig1"
            #    elif freq == "L2C": return "Sig2"
            #    elif freq == "L5": return "Sig3"
            #    else: return np.nan
            #elif const == "IRN": # const name might change, verify!
            #    if freq == "B1": return "Sig1"
            #    else: return np.nan
            else: return np.nan
        
        self.df["Signal"] = self.df["Signal"].astype(str).apply(get_CN0code)
        # Drop nan values in "Signal" column
        self.df.dropna(subset=["Signal"], inplace=True) 

        return self.df 

    def get_ampElev(self):
        """
        Get a standar Amplitude-Elevation dataframe.
        INPUT: amp file, elev file 
        OUTPUT: df  
        """
        # Join dfs: CN0 and Elev
        self.df = self.df_cn.merge(self.df_elv, how='left', on=["TOW [s]", "WNc [w]", "SVID"])
        # Change freq_code (GPS_L1CA) to sig code (Sig1)
        self.df = self._convert_freq2code()
        # Convert GPS to UTC time
        self.df = self.GPS2UTCtime()
        # Decimation 
        self.df = self._decimate_amplitude()
        # Divide 'Signal' column into 3 columns
        # Reindex 
        self.df = self.df.reset_index().set_index(['DateTime', 'SVID', 'Signal']).sort_index()
        # Unstack
        self.df = self.df.unstack(level=-1)
        # Separate
        self.df = self.df.reset_index()
        self.df.set_index("DateTime", inplace=True)
        # Select the min elevation value
        self.df["Elev_"] = self.df["Elev"].apply(lambda x: np.nanmin(x), axis=1)
        del self.df[("Elev","Sig1")]
        del self.df[("Elev","Sig2")]
        del self.df[("Elev","Sig3")]
        self.df.set_axis(["PRN", "CN0_sig1", "CN0_sig2", "CN0_sig3", "Elev"], axis=1)
        # Sort values by "PRN"
        self.df = self.df.reset_index().sort_values(by=["PRN", "DateTime"]).set_index("DateTime")
        # Reorder columns 
        columnsTitles = ['PRN', 'Elev', 'CN0_sig1', 'CN0_sig2','CN0_sig3']
        self.df = self.df.reindex(columns=columnsTitles)
        
        return self.df 
    
    def inputFile_info(self):
        """
        Print input file information.
        """
        with open(self.input_file_path, newline="") as f:
            reader = csv.reader(f)
            rows_target = [1,2]
            j = 0
            info = []
            for row in reader:
                if j <= max(rows_target):
                    if j in rows_target:
                        info += row
                else:
                    break
                j += 1 
        
        info = "__FILE INFO________\n" + "\n".join(info) + "\n___________________"
        return print(info) 

    def check_columns(self):
        """
        Print available column names 
        """
        return print(self.df.columns)
    
    def select_columns(self, cols):
        self.df = self.df.iloc[:,cols]
        return self.df 

    def filter_column(self, columnName="Signal", value="GPS_L1CA"):
        """
        Filter a 'value' from an specific 'columnName' of a df. 
        INPUT: columnName, value
        OUTPUT: df 
        """
        mask = self.df[columnName]==value
        self.df = self.df[mask]
        return self.df 

    def power_intensity(self):
        """
        Get power intensity in dB, from IQ components.
        INPUT: df, with I and Q components     
        """
        def intensity(row):
            value_i = row[0]
            value_q = row[1]
            amplitude = value_i**2 + value_q**2
            return 10*mt.log10(amplitude) # dB
        self.df["Amp"] = self.df[["I","Q"]].apply(intensity,axis=1)
        return self.df 
    
    def GPS2UTCtime(self):
        """
        Convert GPS (WN + TOW)
        INPUT: df (implicit)
        OUPUT: df
        """
        def gps2utc(row):
            leapseconds = 0 # change
            gpsseconds = int(row[0])
            gpsweek = int(row[1])

            datetimeformat = "%Y-%m-%d %H:%M:%S"
            first_epoch = datetime.datetime.strptime("1980-01-06 00:00:00",datetimeformat)
            elapsed = datetime.timedelta(days=(gpsweek*7),seconds=(gpsseconds-leapseconds))
            
            return first_epoch + elapsed
        newDate = self.df.iloc[:,[0,1]].apply(gps2utc, axis=1)
        # Create a new column at position 0
        self.df.insert(0, column="DateTime", value=newDate)
        # Remove some columns
        del self.df["TOW [s]"]
        del self.df["WNc [w]"]
        # Set datetime as index 
        self.df.set_index("DateTime", inplace=True)
        
        return self.df

    def _decimate_amplitude(self):
        """
        Decimate 2 samples per minute: min & max values.
        INPUT: df, with DateTime index and columns: SVID, 
               Signal, CN0, Elev.
        OUTPUT: df 
        """
        # Set multiindex  
        self.df = self.df.reset_index().set_index(['SVID', 'Signal', 'DateTime']).sort_index()
        # Get max & min amplitude and elevation values over a 1m interval     
        level_values = self.df.index.get_level_values
        self.df = (self.df.groupby([level_values(i) for i in [0,1]]
                            +[pd.Grouper(freq='T', level=-1)]).agg(["min", "max"]))
        # Flatten and rename columns 
        index1 = self.df.columns.get_level_values(0)
        index2 = self.df.columns.get_level_values(1)

        new_columns = []
        for i in range(4):
            value = index1[i] + "_" + index2[i]
            new_columns.append(value)

        self.df.columns = new_columns

        # Reset index 
        self.df = self.df.reset_index().set_index("DateTime").sort_index()

        # Merge min & max values in a single column, and decrease the T=30s
        # min
        df_min = self.df.iloc[:,[0,1,2,4]]
        df_min.rename(columns={"CN0_min":"CN0", "Elev_min": "Elev"}, inplace = True)    
        # max
        df_max = self.df.iloc[:,[0,1,3,5]]
        df_max.rename(columns={"CN0_max":"CN0", "Elev_max": "Elev"}, inplace = True)
        # Add 30s to the index 
        df_max.index += datetime.timedelta(seconds=30)
        # Join 
        self.df = pd.concat([df_min, df_max])
        self.df.sort_index(inplace=True)
        self.df.sort_values(by=["SVID","Signal"])

        return self.df 

    def decimate_amplitude_aux(self):
        """
        Decimate 2 samples per minute: min & max values.

        """
        # Resampling each minute: min & max values  
        self.df = self.df.resample("T").agg(["min", "max"])
        # Delete unused columns 
        del self.df["I"]
        del self.df["Q"]
        del self.df["Signal", "min"]
        del self.df["SVID", "min"]
        # Rename columns 
        index1 = self.df.columns.get_level_values(0)
        index2 = self.df.columns.get_level_values(1)
        new_columns = []
        for i in range(4):
            if i<2:
                value = index1[i]
            else:
                value = index1[i] + "_" + index2[i]
            new_columns.append(value)
        self.df.columns = new_columns
        # Create the df 
        df_min = self.df.iloc[:,0:3]
        df_min.rename(columns={"Amp_min":"Amp"}, inplace=True)
        
        df_max = self.df.iloc[:,[0,1,3]]
        df_max.rename(columns={"Amp_max":"Amp"}, inplace=True)
        df_max.index += datetime.timedelta(seconds=30)
        
        self.df = pd.concat([df_min, df_max])
        self.df.sort_index(inplace=True)

        return self.df 

    def get_date(self):
        """
        Get df date
        """
        fecha = self.df.index[0]
        fecha_s = datetime.datetime.strftime(fecha, "%y/%m/%d")
        return fecha_s

    def plot_fast(self, col="Amp"):
        """
        Plot a column from a df. GPS|G03
        """
        mask = self.df["PRN"]=="G03"
        df_p = self.df[mask]
        df_p[col].plot()
        plt.xlabel("Time UTC")
        plt.ylabel("Signal Intensity (dB)")
        plt.title("Signal Intensity (dB)")
        plt.title("GPS|G3", loc="right")
        plt.title(f"{self.get_date()}", loc='left')
        plt.grid(which='both')
        plt.savefig("test.png")

        return 'Ok'

class PlotsISMR():
    def __init__(self, dataframe, ismr_file_name):
        self.df = dataframe
        self.file_name = ismr_file_name # e.g. ljic219b15.20_.ismr
    
    # PLOT HELPER METHODS 
    # ------------ 
    # Check no null column in the frequency column
    def _check_noNull_values(self, const, freq):
        mask = self.df["PRN"].str.contains(const)
        df_aux = self.df[mask]
        if df_aux[freq].isna().sum() < len(df_aux):
            return True 
        else:
            return False

    def get_station_name(self):
        """
        Get the station name based on the station code.
        Add other stations names if neccessary. 
        """
        station_code = self.file_name[:4]
        if station_code == "ljic":
            return "Jicamarca"
        elif station_code == "lsba":
            return "San-Bartolomé"
        else:
            return "" 

    def get_output_figure_name(self):
        station = self.file_name[:4]
        doy = self.file_name[4:7]
        yy = self.file_name[-8:-6]
        fecha_s = doy + "/" + yy 
        fecha = datetime.datetime.strptime(fecha_s, "%j/%y")
        fecha_new = datetime.datetime.strftime(fecha, "%y%m%d")
        new_figure_name = station + "_" + fecha_new
        return new_figure_name

    # Extract PRNs of a constellation and freq, in which there is no null data    
    def extract_prns(self, const='G', freq='CN0_sig1'): # const: char (e.g. 'G')
        prns = self.df["PRN"].unique().tolist()
        PRNs = [value for value in prns if const in value]
        PRNs.sort(key=lambda x: int(x[1:])) # sort in ascendent order 
        
        # Check no null columns in the prns
        prn_values = []
        for value in PRNs:
            mask = self.df["PRN"] == value
            df_test = self.df[mask]
            if df_test[freq].isna().sum() < len(df_test): # when the column is not null 
                prn_values.append(value)
        
        return prn_values

    # Extract info from any variable such as: elevation or CN0
    def get_variable(self, prn='G10', var='CN0_sig1'):
        """ Get the values of a given variable, for each PRN
        """
        mask = self.df["PRN"]==prn
        df_aux = self.df[mask]
        df_final = df_aux[var]
        return df_final

    def all_prns(self, const='G'):
        if const=='G':
            list_prns = [f'G{i+1:02d}' for i in range(32)]
        elif const=='E':
            list_prns = [f'E{i+1:02d}' for i in range(36)]
        else:
            list_prns = []
        return list_prns

    # Convert SBAS code to SVID (number only)
    def _convert2SVID(self, prn='G10'):
        if prn[0] == "S":
            nn = int(prn[1:])
            if 20 <= nn <= 40:
                return str(nn + 100)
            elif 41 <= nn <= 58:
                return str(nn + 157)
            else:
                return str(nn)
        else:
            return prn

    # Get the frequency name and value for a given PRN code and Freq code
    def get_freq_name(self, const='G', freq_code=1):
        if freq_code == 1:
            if const == 'G':
                return {"name":'L1CA', "value":"1575.42"}
            elif const == 'R':
                return {"name":'L1CA', "value":"1602"} # change 
            elif const == 'S':
                return {"name":'L1CA', "value":"1575.42"}
            elif const == 'J':
                return {"name":'L1CA', "value":"1575.42"}
            elif const == 'E':
                return {"name":'L1BC', "value":"1575.42"}
            elif const == 'C':
                return {"name":'B1', "value":"1575.42"}
            elif const == 'I':
                return {"name":'B1', "value":"1176.45"}
            else: 
                return "Insert a right code!"
        elif freq_code == 2:
            if const == 'G':
                return {"name":'L2C', "value":"1227.60"}
            elif const == 'R':
                return {"name":'L2C', "value":"1246"} # change 
            elif const == 'J':
                return {"name":'L2C', "value":"1227.60"}
            elif const == 'E':
                return {"name":'E5a', "value":'1176.45'}
            elif const == 'C':
                return {"name":'B2', "value":'1176.45'}
            elif const == 'S':
                return {"name":'L5', "value":'1176.45'}
            else: 
                return "Insert a right code!"
        elif freq_code == 3:
            if const == 'G':
                return {"name":'L5', "value":'1176.45'}
            elif const == 'J':
                return {"name":'L5', "value":'1176.45'}
            elif const == 'E':
                return {"name":'E5b', "value":'1207.14'}
            elif const == 'C':
                return {"name":'B3', "value":'1268.52'}
            else: 
                return "Insert a right code!"
        else:
            return "Insert a right code!"
        
    # Get the name for a given constelation code
    def get_const_name(self, const='G'):
        if const == 'G': return 'GPS'
        elif const == 'R': return 'GLONASS'
        elif const == 'E': return 'GALILEO'
        elif const == 'S': return 'SBAS'
        elif const == 'C': return 'BEIDOU'
        elif const == 'J': return 'QZSS'
        elif const == 'I': return 'IRNSS'
        else:
            return 'Incorrect PRN code!'

    # Convert GPS into SBAS frequencies    
    def _convert_GPS2SBAS_frequency(self, freq='CN0_sig1'):
        if freq == 'CN0_sig1': return freq
        elif freq == 'CN0_sig3': return 'CN0_sig2'
    
    # Append SBAS prns at the end of the PRN list, only for GPS const 
    def _append_sbas_prns(self, freq, PRNs):
        while freq != 'CN0_sig2':
            freq_sbas = self._convert_GPS2SBAS_frequency(freq)
            PRNs_SBAS = self.extract_prns(const='S', freq=freq_sbas)
            PRNs += PRNs_SBAS
            break
        return PRNs

    # PLOT VARIABLES: CN0, S4
    # --------------
    # Plot CN0 vs time, and elevation vs time (PLOT TYPE I)
    def plotCN0(self, pdf, const='G', freq='CN0_sig1'):
        """
        Input:
        - pdf: object to save into a pdf file  
        """
        if self._check_noNull_values(const, freq): 
            # Get file UTC date
            figure_name = self.get_output_figure_name() # e.g. ljic_200926
            fecha = figure_name[5:] # e.g. 200926
            fecha2 = datetime.datetime.strptime(fecha, "%y%m%d")
            fecha3 = datetime.datetime.strftime(fecha2,"%Y/%m/%d")

            fecha2_tomorrow = fecha2 + pd.DateOffset(days=1)
            fecha2_tomorrow = fecha2_tomorrow.to_pydatetime()

            # Get UTC day range, to add a vertical strip
            fecha_morning_first = fecha2 + pd.DateOffset(hours=11) 
            fecha_morning_first = fecha_morning_first.to_pydatetime()
            
            fecha_morning_last = fecha2 + pd.DateOffset(hours=23)
            fecha_morning_last = fecha_morning_last.to_pydatetime()

            # Get the PRNs
            PRNs = self.extract_prns(const, freq)

            # Append SBAS PRNs for GPS const
            if const=='G': PRNs = self._append_sbas_prns(freq, PRNs)
            
            # Define the A4 page dimentions (landscape)
            fig_width_cm = 29.7      
            fig_height_cm = 21
            inches_per_cm = 1 / 2.54   # Convert cm to inches
            fig_width = fig_width_cm * inches_per_cm  # width in inches
            fig_height = fig_height_cm * inches_per_cm # height in inches
            fig_size = [fig_width, fig_height]
            
            # Create the figure with the subplots 
            n_plots = len(PRNs) + len(PRNs)%2 # Number of subplots with data (even number) 
            n_rows = 6 # Number of available rows p/ page 
            n_cols = 2 # Number of available columns p/ page 
            hratios = [1]*n_rows

            n_plots_left = n_plots
            q = 0
            while n_plots_left > 0: 
                # Determine the number of subplots in the figure 
                if (n_plots_left//(n_rows*n_cols)) > 0:
                    q += 1
                    n_plots2 = n_rows*n_cols
                    PRNs_section = PRNs[:n_rows*n_cols]
                    PRNs = PRNs[n_rows*n_cols:]
                else:
                    n_plots2 = n_plots_left
                    PRNs_section = PRNs

                # Plot
                fig, axs = plt.subplots(n_rows, n_cols, figsize=fig_size, sharex=False, sharey="row",
                                gridspec_kw={'hspace': 0, 'wspace': 0, 'height_ratios':hratios})   
                j = 0

                for ax in axs.reshape(-1): # Plot from left to right, rather than top to bottom 
                    if j < n_plots_left: # Plot
                        # ax -> CN0
                        # ax2 -> elevation
                        ax2 = ax.twinx()
                        
                        # Plot CN0 & elevation data
                        if j < len(PRNs_section):
                            # Plot s4 info
                            prn_value = PRNs_section[j]
                            
                            # -> Get the correct freq for SBAS const, appended to GPS plots
                            if const=='G' and prn_value[0]=='S': 
                                freq_n = self._convert_GPS2SBAS_frequency(freq)
                            else: freq_n = freq
                            
                            color1 = "blue" # This color is used in y axis labels, ticks and border  
                            colors1 = ["cornflowerblue", "navy"] # These colors are used for the plot lines

                            for k in range(2):
                                df3_cn0 = self.get_variable(prn_value, var=freq_n+f"_{k+1}")
                                #df3_cn0 = df3_cn0.sort_index().asfreq("T")
                                ax.plot(df3_cn0.index, df3_cn0.values, '.', color=colors1[k], markersize=2)
                                # Plot the strip day/night
                                ax.set_facecolor(color="lightgrey")
                                ax.axvspan(fecha_morning_first, fecha_morning_last, color="white") # strip morning/night
                            
                            # Plot elevation info
                            df2_elev = self.get_variable(prn_value, var="Elev")
                            #df2_elev = df2_elev.sort_index().asfreq("T") # Resampling each minute
                            color2 = "orange"
                            ax2.plot(df2_elev.index, df2_elev.values, '.', color=color2, markersize=1)
                            
                            # Annotate the prn in the subplot
                            x_location = fecha2 + pd.Timedelta(minutes=30)
                            ax2.text(x_location, 35, self._convert2SVID(prn_value), fontsize=15, weight='roman') # 0.375

                        # Set axis limits 
                        ax.set_xlim([fecha2, fecha2_tomorrow])
                        ax.set_ylim([0,80]) # CN0 (dB-Hz)
                        ax2.set_ylim([0,90]) # Elevation angle (º)

                        # Set ticks and tick labels 
                        # -> Set y axis format, labels odds subplots only
                        len_half_ax = len(axs.T.reshape(-1))/2

                        if j%2 == 1: # change only for the 2nd column    
                            # Set y labels only to even subplots
                            ax.yaxis.set_minor_locator(AutoMinorLocator(4))
                            ax.set_yticks([0,80])
                            ax2.yaxis.set_minor_locator(AutoMinorLocator(4))
                            ax2.set_yticks([0,90])

                            if j%4 == 1: # subsequent subplot  
                                ax.set_yticklabels([0,80])
                                ax2.set_yticklabels([0,90])
                            else:    
                                ax.set_yticklabels(['',''])
                                ax2.set_yticklabels(['',''])

                            # Set yellow color to the right y axis
                            for axis in ['top','bottom','left']:
                                ax.spines[axis].set_linewidth(2)
                                ax2.spines[axis].set_linewidth(2)

                            ax.spines['right'].set_color(color2)
                            ax.spines['right'].set_linewidth(2)
                            ax2.spines['right'].set_color(color2)
                            ax2.spines['right'].set_linewidth(2)
                            ax2.tick_params(axis='y', which='both', colors=color2)

                        else: # apply some changes to the 1st column 
                            # remove y tick labels for elevation 
                            ax2.yaxis.set_minor_locator(AutoMinorLocator(4))
                            ax2.set_yticks([0,90])
                            ax2.set_yticklabels(['',''])

                            # set linewidth to top, bottom and right borders of the subplot
                            for axis in ['top','bottom','right']:
                                ax.spines[axis].set_linewidth(2)
                                ax2.spines[axis].set_linewidth(2)

                            # Set blue color to the left y axis
                            ax.spines['left'].set_color(color1)
                            ax.spines['left'].set_linewidth(2)
                            ax2.spines['left'].set_color(color1)
                            ax2.spines['left'].set_linewidth(2)
                            ax.tick_params(axis='y', which='both', colors=color1)

                        # -> Set x axis format 
                        hours = mdates.HourLocator(interval = 2)
                        ax.xaxis.set_major_locator(hours) # ticks interval: 2h
                        #ax.xaxis.set_major_locator(NullLocator()) # ticks interval: 2h
                        ax.xaxis.set_minor_locator(AutoMinorLocator(2)) # minor tick division: 2
                        myFmt = DateFormatter("%H")
                        ax.xaxis.set_major_formatter(myFmt) # x format: hours 
                        
                        # -> set the ticks style 
                        ax.xaxis.set_tick_params(width=2, length=8, which='major', direction='out')
                        ax.xaxis.set_tick_params(width=1, length=4, which='minor', direction='out')
                        ax.yaxis.set_tick_params(width=2, length=15, which='major', direction='inout')
                        ax.yaxis.set_tick_params(width=1, length=4, which='minor', direction='out')
                        ax2.yaxis.set_tick_params(width=2, length=15, which='major', direction='inout')
                        ax2.yaxis.set_tick_params(width=1, length=4, which='minor', direction='out')

                        # -> set the label ticks 
                        ax.tick_params(axis='x', which='major', labelsize=12)
                        ax.tick_params(axis='y', labelsize=12)
                        ax2.tick_params(axis='y', labelsize=12)

                        if j == (n_plots2-1): # lower right: stay label xticks
                            pass
                        elif j == (n_plots2-2): # lower left: stay label xticks 
                            pass
                        else: # hide label xticks  
                            ax.tick_params(axis='x', which='major', labelsize=12, labelbottom='off')
                            
                        # Set grid
                        ax.grid(which='major', axis='both', ls=':', linewidth=1.2)
                        ax.grid(which='minor', axis='both', ls=':', alpha=0.5)

                        # Set title and axis labels 
                        aux = self.get_freq_name(const, int(freq[-1]))
                        frequency_name = aux["name"]
                        frequency_value = aux["value"] + "MHz"
                        
                        # -> Title 
                        if j == 0: # Subplot on Upper left  
                            fig.text(0, 1, fecha3, ha='left', va='bottom', fontsize=17, weight='semibold', transform=ax.transAxes)
                            fig.text(0.42, 1, self.get_station_name(), ha='left', va='bottom', fontsize=17, weight='semibold', transform=ax.transAxes)   
                                          
                        if j == 1: # Subplot on Upper right
                            fig.text(0, 1.3, 'Amplitude', ha='center', va='bottom', fontsize=19, weight='semibold', transform=ax.transAxes)
                            fig.text(0.3, 1, frequency_value, ha='center', va='bottom', fontsize=17, weight='semibold', transform=ax.transAxes)
                            fig.text(1, 1, f"{frequency_name} | {self.get_const_name(const)}", ha='right', va='bottom', fontsize=17, weight='semibold', transform=ax.transAxes)

                        # -> Labels
                        if j == n_plots2-1: # x axis label, Subplot on Lower right
                            fig.text(0, -0.5, 'Time UTC', ha='center', va='center', fontsize=14, transform=ax.transAxes) 
                        
                        aux_nrows = int(n_plots2/n_cols)
                        if j == aux_nrows-aux_nrows%2: # y axis label on the left
                            k = (aux_nrows%2)*0.5
                            fig.text(-0.1, 1-k, 'C/N0(dB-Hz)', ha='center', va='center', rotation='vertical', fontsize=14, color='b', transform=ax.transAxes)            
                            
                        if j == (aux_nrows+(1-aux_nrows%2)): # y axis label on the right 
                            k = (aux_nrows%2)*0.5
                            fig.text(1.1, 1-k, 'Elevation Angle($^o$)', ha='center', va='center', rotation=-90, fontsize=14, color=color2, transform=ax.transAxes)

                    else:
                        ax.axis('off')

                    j += 1

                # Save figure as pdf
                pdf.savefig()

                n_plots_left -= j
            
            print(f"Plotted successfully; for const: {const}, and freq: {freq}!")
        else:
            print(f"There is only Null data; for const: {const}, and freq: {freq}!") 
        
        return 'Ok!'

   # Plot CN0 vs time, and elevation vs time (PLOT TYPE II)
   # Nº subplots/page = 36; Marker = dash ('-'); line's color = blue;
   # Top = s4 graphs; PRN names = right side
    def plotCN0_2(self, pdf, const='G', freq='CN0_sig1'):
        """
        Input:
        - pdf: object to save into a pdf file  
        """
        if self._check_noNull_values(const, freq): 
            # Get file UTC date
            figure_name = self.get_output_figure_name() # e.g. ljic_200926
            fecha = figure_name[5:] # e.g. 200926
            fecha2 = datetime.datetime.strptime(fecha, "%y%m%d")
            fecha3 = datetime.datetime.strftime(fecha2,"%Y/%m/%d")

            fecha2_tomorrow = fecha2 + pd.DateOffset(days=1)
            fecha2_tomorrow = fecha2_tomorrow.to_pydatetime()

            # Get UTC day range, to add a vertical strip
            fecha_morning_first = fecha2 + pd.DateOffset(hours=11) 
            fecha_morning_first = fecha_morning_first.to_pydatetime()
            
            fecha_morning_last = fecha2 + pd.DateOffset(hours=23)
            fecha_morning_last = fecha_morning_last.to_pydatetime()

            # Get the PRNs
            #PRNs = self.extract_prns(const, freq)
            PRNs = self.all_prns(const)

            # Append SBAS PRNs for GPS const
            if const=='G': PRNs = self._append_sbas_prns(freq, PRNs)
            
            # Define the A4 page dimentions (landscape)
            fig_width_cm = 29.7      
            fig_height_cm = 21
            inches_per_cm = 1 / 2.54   # Convert cm to inches
            fig_width = fig_width_cm * inches_per_cm  # width in inches
            fig_height = fig_height_cm * inches_per_cm # height in inches
            fig_size = [fig_width, fig_height]
            
            # Create the figure with the subplots 
            n_plots = len(PRNs) + len(PRNs)%2 # Number of subplots with data (even number) 
            n_rows = 18 # Number of available rows p/ page 
            n_cols = 2 # Number of available columns p/ page 
            hratios = [1]*n_rows

            n_plots_left = n_plots
            q = 0
            while n_plots_left > 0: 
                # Determine the number of subplots in the figure 
                if (n_plots_left//(n_rows*n_cols)) > 0:
                    q += 1
                    n_plots2 = n_rows*n_cols
                    PRNs_section = PRNs[:n_rows*n_cols]
                    PRNs = PRNs[n_rows*n_cols:]
                else:
                    n_plots2 = n_plots_left
                    PRNs_section = PRNs

                # Plot
                fig, axs = plt.subplots(n_rows, n_cols, figsize=fig_size, sharex=False, sharey=False,
                                gridspec_kw={'hspace': 0, 'wspace': 0, 'height_ratios':hratios})   
                j = 0

                for ax in axs.reshape(-1): # Plot from left to right, rather than top to bottom 
                    if j < n_plots_left: # Plot
                        # ax -> elevation
                        # ax2 -> CN0
                        ax2 = ax.twinx()
                        
                        # Change y axis positions 
                        ax.yaxis.set_label_position("right")
                        ax.yaxis.tick_right()
                        ax2.yaxis.set_label_position("left")
                        ax2.yaxis.tick_left()

                        # Plot CN0 & elevation data
                        if j < len(PRNs_section):
                            # Plot s4 info
                            prn_value = PRNs_section[j]
                            
                            # -> Get the correct freq for SBAS const, appended to GPS plots
                            if const=='G' and prn_value[0]=='S': 
                                freq_n = self._convert_GPS2SBAS_frequency(freq)
                            else: freq_n = freq
                            
                            color1 = "blue" # This color is used in y axis labels, ticks and border  
                            colors1 = ["navy"]*2 #["cornflowerblue", "navy"] # These colors are used for the plot lines

                            for k in range(2):
                                df3_cn0 = self.get_variable(prn_value, var=freq_n+f"_{k+1}")
                                df3_cn0 = df3_cn0.sort_index().asfreq("T") # resampling each minute
                                ax2.plot(df3_cn0.index, df3_cn0.values, '-', color=colors1[k], markersize=2)
                                # Plot the strip day/night
                                ax.set_facecolor(color="lightgrey")
                                ax.axvspan(fecha_morning_first, fecha_morning_last, color="white") # strip morning/night
                            
                            # Plot elevation info
                            df2_elev = self.get_variable(prn_value, var="Elev")
                            df2_elev = df2_elev.sort_index().asfreq("T") # Resampling each minute
                            color2 = "orange"
                            ax.plot(df2_elev.index, df2_elev.values, '-', color=color2, markersize=1)
                            
                            # Annotate the prn in the subplot
                            x_location = fecha2 + pd.Timedelta(hours=21, minutes=30)
                            ax.text(x_location, 51, self._convert2SVID(prn_value), fontsize=12, weight='roman') # 0.375

                        # Set axis limits 
                        ax.set_xlim([fecha2, fecha2_tomorrow])
                        ax.set_ylim([0,90]) # Elevation angle (º)
                        ax2.set_ylim([0,80]) # CN0 (dB-Hz)
                        
                        ax.yaxis.set_minor_locator(AutoMinorLocator(4))
                        ax.set_yticks([0,90])
                        ax2.yaxis.set_minor_locator(AutoMinorLocator(4))
                        ax2.set_yticks([0,80])

                        if j%2 == 0: # first column 
                            ax.set_yticklabels(['',''])
                            if j%4 == 0:
                                ax2.set_yticklabels([0,80])
                            else:
                                ax2.set_yticklabels(['',''])
                            
                            # set linewidth to top, bottom and right borders of the subplot
                            for axis in ['top','bottom','right','left']:
                                ax.spines[axis].set_linewidth(2)
                                ax2.spines[axis].set_linewidth(2)
                            # set color for left spin
                            ax2.spines['left'].set_color(color1)
                            ax2.tick_params(axis='y', which='both', colors=color1) # tick and tick label color

                        else: # second column 
                            ax2.set_yticklabels(['',''])
                            if j%4 == 1:
                                ax.set_yticklabels([0,90])
                            else:
                                ax.set_yticklabels(['',''])
                            
                            # set linewidth to top, bottom and right borders of the subplot
                            for axis in ['top','bottom','right','left']:
                                ax.spines[axis].set_linewidth(2)
                                ax2.spines[axis].set_linewidth(2)

                            # set color for right spin
                            ax2.spines['right'].set_color(color2)
                            ax.tick_params(axis='y', which='both', colors=color2) # tick and tick label color
                        
                        # -> Set x axis format 
                        hours = mdates.HourLocator(interval = 2)
                        ax.xaxis.set_major_locator(hours) # ticks interval: 2h
                        #ax.xaxis.set_major_locator(NullLocator()) # ticks interval: 2h
                        ax.xaxis.set_minor_locator(AutoMinorLocator(2)) # minor tick division: 2
                        myFmt = DateFormatter("%H")
                        ax.xaxis.set_major_formatter(myFmt) # x format: hours 
                        
                        # -> set the ticks style 
                        ax.xaxis.set_tick_params(width=2, length=8, which='major', direction='out')
                        ax.xaxis.set_tick_params(width=1, length=4, which='minor', direction='out')
                        ax.yaxis.set_tick_params(width=2, length=15, which='major', direction='inout')
                        ax.yaxis.set_tick_params(width=1, length=8, which='minor', direction='inout')
                        ax2.yaxis.set_tick_params(width=2, length=15, which='major', direction='inout')
                        ax2.yaxis.set_tick_params(width=1, length=8, which='minor', direction='inout')

                        # -> set the label ticks 
                        ax.tick_params(axis='x', which='major', labelsize=12)
                        ax.tick_params(axis='y', labelsize=12)
                        ax2.tick_params(axis='y', labelsize=12)

                        if j == (n_plots2-1): # lower right: stay label xticks
                            pass
                        elif j == (n_plots2-2): # lower left: stay label xticks 
                            pass
                        else: # hide label xticks  
                            ax.tick_params(axis='x', which='major', labelsize=12, labelbottom='off')
                            
                        # Set grid
                        ax.grid(which='major', axis='both', ls=':', linewidth=1.2)
                        ax.grid(which='minor', axis='both', ls=':', alpha=0.5)

                        # Set title and axis labels 
                        aux = self.get_freq_name(const, int(freq[-1]))
                        frequency_name = aux["name"]
                        frequency_value = aux["value"] + "MHz"
                        
                        # -> Title 
                        if j == 0: # Subplot on Upper left  
                            fig.text(0, 1, fecha3, ha='left', va='bottom', fontsize=17, weight='semibold', transform=ax.transAxes)
                            fig.text(0.42, 1, self.get_station_name(), ha='left', va='bottom', fontsize=17, weight='semibold', transform=ax.transAxes)   
                                          
                        if j == 1: # Subplot on Upper right
                            fig.text(0, 1.7, 'Amplitude', ha='center', va='bottom', fontsize=19, weight='semibold', transform=ax.transAxes)
                            fig.text(0.3, 1, frequency_value, ha='center', va='bottom', fontsize=17, weight='semibold', transform=ax.transAxes)
                            fig.text(1, 1, f"{frequency_name} | {self.get_const_name(const)}", ha='right', va='bottom', fontsize=17, weight='semibold', transform=ax.transAxes)

                        # -> Labels
                        if j == n_plots2-1: # x axis label, Subplot on Lower right
                            fig.text(0, -1.35, 'Time UTC', ha='center', va='center', fontsize=14, transform=ax.transAxes) 
                        
                        aux_nrows = int(n_plots2/n_cols)
                        if j == aux_nrows-aux_nrows%2: # y axis label on the left
                            k = (aux_nrows%2)*0.5
                            fig.text(-0.11, 1-k, 'C/N0(dB-Hz)', ha='center', va='center', rotation='vertical', fontsize=14, color='b', transform=ax.transAxes)            
                            
                        if j == (aux_nrows+(1-aux_nrows%2)): # y axis label on the right 
                            k = (aux_nrows%2)*0.5
                            fig.text(1.11, 1-k, 'Elevation Angle($^o$)', ha='center', va='center', rotation=-90, fontsize=14, color=color2, transform=ax.transAxes)

                    else:
                        ax.axis('off')

                    j += 1

                # Save figure as pdf
                pdf.savefig()

                n_plots_left -= j
            
            print(f"Plotted successfully; for const: {const}, and freq: {freq}!")
        else:
            print(f"There is only Null data; for const: {const}, and freq: {freq}!") 
        
        return 'Ok!'
