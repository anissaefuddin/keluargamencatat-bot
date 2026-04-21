from dataclasses import dataclass, field
from typing import Literal

Tipe = Literal["pemasukan", "pengeluaran"]
Source = Literal["text", "photo", "voice"]


@dataclass
class TxnDraft:
    nominal: int
    tipe_transaksi: Tipe
    kategori: str
    keterangan: str
    confidence: float
    raw_input: str
    source: Source = "text"
    pengguna: str = ""


@dataclass
class TxnRow:
    id_transaksi: str
    tanggal: str
    tipe_transaksi: str
    kategori: str
    nominal: int
    keterangan: str
    pengguna: str

    def as_list(self) -> list:
        return [
            self.id_transaksi,
            self.tanggal,
            self.tipe_transaksi,
            self.kategori,
            self.nominal,
            self.keterangan,
            self.pengguna,
        ]

    @classmethod
    def headers(cls) -> list[str]:
        return [
            "id_transaksi",
            "tanggal",
            "tipe_transaksi",
            "kategori",
            "nominal",
            "keterangan",
            "pengguna",
        ]
