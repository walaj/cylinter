import os
import sys
import yaml
import logging

import pandas as pd

from ..utils import input_check, read_markers, get_filepath, reorganize_dfcolumns

logger = logging.getLogger(__name__)


def aggregateData(data, self, args):

    print()

    print("1")
    check, markers_filepath = input_check(self)
    print("A")
    markers, abx_channels = read_markers( 
        markers_filepath=markers_filepath,
        counterstain_channel=self.counterstainChannel,
        markers_to_exclude=self.markersToExclude, data=None
    )

    print("2")
    # initialize CyLinter QC report if it hasn't been already
    report_path = os.path.join(self.outDir, 'cylinter_report.yml')
    if not os.path.exists(report_path):
        f = open(report_path, 'w')
        yaml.dump({}, f)

    print("3")        
    df_list = []
    channel_setlist = []
    sample_keys = [i for i in self.sampleNames.keys()]
    for key in sample_keys:

        if check == 'standard':
            sample = key
        else:
            sample = key.split('--')[0]

        if sample not in self.samplesToExclude:

            logger.info(f'IMPORTING sample {key}')

            print(check)
            print(sample)
            file_path = get_filepath(self, check, sample, 'CSV')
            csv = pd.read_csv(file_path)

            # drop markers in markersToExclude config parameter
            csv.drop(
                columns=[i for i in self.markersToExclude
                         if i in csv.columns], axis=1, inplace=True)

            # select boilerplate columns
            cols = (
                [i for i in [j for j in markers['marker_name']] +
                 [i for i in ['CellID', 'X_centroid', 'Y_centroid', 'Area', 'MajorAxisLength',
                              'MinorAxisLength', 'Eccentricity', 'Solidity', 'Extent', 
                              'Orientation'] if i in csv.columns]]
            )

            try:
                csv = csv[cols]
            except KeyError as e:
                logger.info(
                    f'Aborting; some (or all) marker names in markers.csv for sample {sample} do not appear as columns in the single-cell data table. Check for spelling and case.'
                )
                print(e)
                sys.exit()

            # (for SARDANA)
            # trim mask object names from column headers
            # cols_update = [
            #     i.rsplit('_', 1)[0] if 'Mask' in i else
            #     i for i in csv.columns
            # ]
            # csv.columns = cols_update

            # add sample column
            csv['Sample'] = sample

            # add condition column
            csv['Condition'] = self.sampleConditionAbbrs[key]

            # add replicate column
            csv['Replicate'] = self.sampleReplicates[key]

            # append dataframe to list
            df_list.append(csv)

            # append the set of csv columns for sample to a list
            # this will be used to select columns shared among samples
            channel_setlist.append(set(csv.columns))

        else:
            logger.info(f'censoring sample {sample}')
    print()

    # stack dataframes row-wise
    data = pd.concat(df_list, axis=0)
    del df_list

    # only select channels shared among all samples
    channels_set = list(set.intersection(*channel_setlist))

    print("4")
    logger.info(f'{len(data.columns)} total columns')
    logger.info(f'{len(channels_set)} columns in common between all samples')

    before = set(data.columns)
    after = set(channels_set)
    if len(before.difference(after)) == 0:
        pass
    else:
        markers_to_drop = list(before.difference(after))
        print()
        logger.warning(
            f'Columns {markers_to_drop} are not in all'
            ' samples and will be dropped from downstream analysis.'
        )
    data = data[channels_set].copy()

    # sort by Sample and CellID to be tidy
    data.sort_values(by=['Sample', 'CellID'], inplace=True)

    # assign global index
    data.reset_index(drop=True, inplace=True)

    # ensure MCMICRO-generated columns come first and
    # are in the same order as csv feature tables
    data = reorganize_dfcolumns(data, markers, self.dimensionEmbedding)

    print()
    print()
    return data
