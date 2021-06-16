#!/home/luis/anaconda3/bin/python3
#___________________________________________________________
#                  AMPLITUDE vs TIME 
#                        plots
#                        v2.0
#-----------------------------------------------------------
# This script creates Amplitude vs Time plots, for each 
# frequency and constellation. Sampling time (Ts) is 
# increased to 30s, with the min & max values over a 
# period of minute. SBAS data is included in GPS const 
# by default. Elevation vs Time plots are also included 
# in the same graphs. These plots are saved in an A4 pdf 
# file.
# INPUT FILES: MeasEpoch2 & ChannelStatus ASCCI FILES.   
# Author: Luis D.
# :)
from matplotlib.backends.backend_pdf import PdfPages
from septentrio_tools import ProcessSBF as sbf
from septentrio_tools import PlotsISMR
import glob 
import os 

root_path = "/home/luis/Desktop/Proyects_Files/LISN/GPSs/Tareas/Graficas_desvanecimientos/other/lower_sampling/"
input_files_path = root_path + "Input_data/Data_set/"
input_files_path_op = root_path + "Input_data/Data_procesada/"
output_files_path = root_path + "Output_data/"

def process_dataframe(input_file_cn, input_file_elv):
    file1 = sbf()
    file1.read_channelStatus(input_file_elv)
    file1.read_measEpoch(input_file_cn)
    df = file1.get_ampElev()
    #print(df.head())
    # Filter df based on elevation col 
    for j in range(3):
        j += 1
        file1.filter_dataframe(col=f"CN0_sig{j}", on="Elev", threshold=35, new_col_name=[f"CN0_sig{j}_1", f"CN0_sig{j}_2"])

    df = file1.df
    print("df ready to plot!")

    return df

def main():
    # Specify the const and freq to plot    
    const_list = ['G', 'E']   
    freq_list = ['CN0_sig1', 'CN0_sig2', 'CN0_sig3'] 

    list_aux = glob.glob(input_files_path + "*.txt")
    list_aux2 = [file[len(input_files_path): len(input_files_path) + 17] for file in list_aux]
    list_input_files = list(set(list_aux2))
    list_input_files.sort() # e.g. ['ljic3240.20__SBF_', 'ljic3250.20__SBF_']

    if len(list_input_files) > 0:
        for file_i in list_input_files:
            # Get the df
            file_cn = input_files_path + file_i + "MeasEpoch2.txt"
            file_elv =  input_files_path + file_i + "ChannelStatus.txt"
            df = process_dataframe(file_cn, file_elv)
            
            # Plot
            #input_file_name = file_i[len(input_files_path):]
            g1 = PlotsISMR(dataframe=df, ismr_file_name=file_i)
            # -> Create an empty pdf file to save the plots
            figure_name = g1.get_output_figure_name() + "_CN0.pdf" # e.g. ljic_200806_CN0.pdf
            pdf = PdfPages(output_files_path + figure_name)
            # -> Generate the plots
            for c in const_list:
                for f in freq_list:         
                    g1.plotCN0(const=c, freq=f, pdf=pdf)
            pdf.close()

            # Move input files to a permanent directory
            os.rename(file_cn, input_files_path_op + file_i + "MeasEpoch2.txt")
            os.rename(file_elv, input_files_path_op + file_i + "ChannelStatus.txt")
    
    return 'Ok'

if __name__ == '__main__':
    print("STARTING...")
    main()
    print("FINISHED ----------")