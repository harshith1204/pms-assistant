import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DetailWorkitemComponent } from './detail-workitem.component';

describe('DetailWorkitemComponent', () => {
  let component: DetailWorkitemComponent;
  let fixture: ComponentFixture<DetailWorkitemComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DetailWorkitemComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DetailWorkitemComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
