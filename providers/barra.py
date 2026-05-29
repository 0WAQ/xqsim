from static_provider import *


class Provider(StaticProvider):
    def __init__(self, *args):
        super().__init__(*args)
        self.db_name = "barra"
        self.abbr = "barra"
        self.factor_dict = {}
        self.mysql_config = "mysql_235.json"

    def generate_matrix(self):
        table_name_dict = {
            "Asset_Data": {
                "yield": "`Yield%` / 100",
                "total_risk": "`TotalRisk%` / 100",
                "spec_risk": "`SpecRisk%` / 100",
                "hist_beta": "HistBeta",
                "pred_beta": "PredBeta"
            },
            "Asset_DlySpecRet": {
                "specific_return": "SpecificReturn"
            },
            "Asset_LSR": {
                "root_specific_risk": "RootSpecificRisk"
            },
            "Asset_UnadjSpecificRisk": {
                "unadj_spec_risk": "`UnadjSpecRisk%` / 100"
            },
            "Daily_Asset_Price": {
                "price": "Price",
                "capt": "Capt",
                "dly_return": "`DlyReturn%` / 100"
            },
            "ESTU_POR": {
                "shares": "Shares"
            }
        }

        for table_name, name_dict in table_name_dict.items():
            self.generate_matrix_with_name_dict(db_name=self.db_name,
                                                table_name=table_name,
                                                name_dict=name_dict,
                                                date_name="DataDate",
                                                date_find=False,
                                                code_name="S_INFO_WINDCODE",
                                                code_find=True,
                                                abbr=self.abbr)

    def generate_industry(self):
        sql = """
            SELECT DISTINCT e.DataDate AS TradingDay, e.S_INFO_WINDCODE AS WindCode, f.FactorNum AS `level1`
            FROM barra.Asset_Exposure e 
            JOIN barra.Factors f ON e.Factor = f.Factor AND f.FactorGroup = '2-Industries'
            WHERE e.DataDate BETWEEN '%s' AND '%s'
            """ % (self.meta.begin_trading_day, self.meta.end_trading_day)
        self.generate_matrix_from_sql(sql=sql,
                                      name_dict={"level1": "level1"},
                                      date_find=False,
                                      code_find=True,
                                      abbr=self.abbr)

    def get_factor_dict(self):
        sql = """SELECT FactorNum - 1 AS FactorNum , Factor FROM barra.Factors"""
        for row in self.exec_sql_fetchall(sql):
            self.factor_dict[row["Factor"]] = int(row["FactorNum"])
        log_info("Factor size %s", len(self.factor_dict))

    def generate_dly_factor_return(self):
        sql = """
            SELECT DataDate AS TradingDay, Factor, DlyReturn as dly_factor_return
            FROM barra.DlyFacRet
            WHERE DataDate BETWEEN '%s' AND '%s'
            """ % (self.meta.begin_trading_day, self.meta.end_trading_day)
        array = np.full((self.meta.di_size, len(self.factor_dict)), NAN, np.float64)
        for row in self.exec_sql_fetchall(sql):
            trading_day = int(row["TradingDay"])
            di = self.meta.offset_di_mapping[trading_day]
            factor = self.factor_dict[row["Factor"]]
            array[di][factor] = row["dly_factor_return"]
        self.write_data(self.abbr + ".dly_factor_return", array)

    def generate_exposure(self):
        batch_size = 50
        for di in range(self.meta.begin_di, self.meta.end_di + 1, batch_size):
            start_di = di
            end_di = min(di + batch_size - 1, self.meta.end_di)
            begin_trading_day = self.meta.date_index[start_di]
            end_trading_day = self.meta.date_index[end_di]
            sql = """
                SELECT DISTINCT DataDate AS TradingDay, S_INFO_WINDCODE AS WindCode, Factor, Exposure
                FROM barra.Asset_Exposure
                WHERE DataDate BETWEEN '%s' AND '%s'
                """ % (begin_trading_day, end_trading_day)

            exposure_array = np.full((end_di - start_di + 1, self.meta.ii_size, len(self.factor_dict)), NAN, np.float64)

            for row in self.exec_sql_fetchall(sql):
                trading_day = int(row["TradingDay"])
                code = row["WindCode"]
                di = self.meta.total_di_mapping[trading_day] - start_di
                if code not in self.meta.ii_mapping:
                    continue
                ii = self.meta.ii_mapping[code]
                factor = row["Factor"]
                exposure_array[di][ii][self.factor_dict[factor]] = row["Exposure"]

            self.write_compress_data(self.abbr + ".exposure", exposure_array, begin_trading_day, end_trading_day)

    def generate_covariance(self, dbname, data_name):
        sql = """
                SELECT Factor1, Factor2, VarCovar, DataDate AS TradingDay
                FROM barra.%s
                WHERE DataDate BETWEEN '%s' AND '%s'
                """ % (dbname, self.meta.begin_trading_day, self.meta.end_trading_day)

        covariance_array = np.full((self.meta.di_size, len(self.factor_dict), len(self.factor_dict)), NAN, np.float64)
        for row in self.exec_sql_fetchall(sql):
            trading_day = int(row["TradingDay"])
            di = self.meta.offset_di_mapping[trading_day]
            factor1 = self.factor_dict[row["Factor1"]]
            factor2 = self.factor_dict[row["Factor2"]]
            covariance_array[di][factor1][factor2] = row["VarCovar"]
            covariance_array[di][factor2][factor1] = row["VarCovar"]
        self.write_data(self.abbr + "." + data_name, covariance_array)

    def generate(self):
        self.generate_matrix()
        self.generate_industry()

        self.get_factor_dict()
        self.generate_dly_factor_return()
        self.generate_exposure()
        self.generate_covariance("Covariance", "covariance")
        self.generate_covariance("preVRACovariance", "pre_vra_covariance")
        self.generate_covariance("UnadjCovariance", "unadj_covariance")


def main():
    builder_run(meta_dir="/cc", begin_date=20201208, end_date=20201231, output_cache_dir="./cc_update")


if __name__ == '__main__':
    main()
